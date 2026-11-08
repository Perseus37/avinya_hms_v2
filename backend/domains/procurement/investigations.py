"""Human-owned reconciliation investigation lifecycle.

Source references are polymorphic and deliberately not foreign keys. The source
record remains in its owning procurement table; this case stores a stable source
type/id/reference and never copies patient or bank-account payloads.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.domains.identity.models import User
from backend.domains.procurement.models import (
    BankStatementLine,
    ReconciliationInvestigation,
    ReconciliationInvestigationEvent,
    ReconciliationSLAPolicy,
    SupplierPayment,
    SupplierPaymentRequest,
)

router = APIRouter()


class SLAPolicyCreate(BaseModel):
    severity: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    target_minutes: int = Field(gt=0, le=525600)
    warning_percent: int = Field(default=80, ge=1, le=99)


class InvestigationCreate(BaseModel):
    candidate_type: str = Field(min_length=3, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    source_type: str = Field(pattern=r"^(BANK_STATEMENT_LINE|SUPPLIER_PAYMENT|SUPPLIER_PAYMENT_REQUEST)$")
    source_id: int = Field(gt=0)
    source_reference: Optional[str] = Field(default=None, max_length=160)
    title: str = Field(min_length=5, max_length=180)
    summary: str = Field(min_length=10, max_length=4000)
    severity: str = Field(default="MEDIUM", pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")


class InvestigationAssign(BaseModel):
    assigned_to_id: int = Field(gt=0)
    expected_version: int = Field(ge=1)
    note: Optional[str] = Field(default=None, max_length=1000)


class InvestigationTransition(BaseModel):
    to_status: str = Field(pattern=r"^(IN_REVIEW|RESOLVED|DISMISSED)$")
    expected_version: int = Field(ge=1)
    resolution: Optional[str] = Field(default=None, max_length=4000)
    root_cause: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=1000)


class InvestigationReopen(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=2000)


class InvestigationQualityReview(BaseModel):
    expected_version: int = Field(ge=1)
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")
    note: Optional[str] = Field(default=None, max_length=2000)


def _source_model(source_type: str):
    return {
        "BANK_STATEMENT_LINE": BankStatementLine,
        "SUPPLIER_PAYMENT": SupplierPayment,
        "SUPPLIER_PAYMENT_REQUEST": SupplierPaymentRequest,
    }[source_type]


def _sla_state(row: ReconciliationInvestigation) -> str:
    if row.sla_due_at is None:
        return "NOT_CONFIGURED"
    now = datetime.now(timezone.utc)
    due = row.sla_due_at if row.sla_due_at.tzinfo else row.sla_due_at.replace(tzinfo=timezone.utc)
    if row.status in {"RESOLVED", "DISMISSED"}:
        closed = row.resolved_at or row.updated_at
        return "CLOSED_ON_TIME" if closed and closed <= due else "CLOSED_LATE"
    if now >= due:
        return "BREACHED"
    started = row.sla_started_at or row.opened_at
    if started and row.sla_warning_percent:
        total = max((due - started).total_seconds(), 1)
        elapsed = max((now - started).total_seconds(), 0)
        if elapsed / total * 100 >= row.sla_warning_percent:
            return "WARNING"
    return "ON_TRACK"


def _case_payload(row: ReconciliationInvestigation) -> dict:
    return {
        "id": row.id,
        "external_key": row.external_key,
        "candidate_type": row.candidate_type,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "source_reference": row.source_reference,
        "title": row.title,
        "summary": row.summary,
        "severity": row.severity,
        "status": row.status,
        "opened_by_id": row.opened_by_id,
        "assigned_to_id": row.assigned_to_id,
        "resolution": row.resolution,
        "root_cause": row.root_cause,
        "opened_at": row.opened_at,
        "updated_at": row.updated_at,
        "resolved_at": row.resolved_at,
        "closed_by_id": row.closed_by_id,
        "reopen_count": row.reopen_count,
        "resolution_quality_status": row.resolution_quality_status,
        "resolution_quality_reviewed_by_id": row.resolution_quality_reviewed_by_id,
        "resolution_quality_reviewed_at": row.resolution_quality_reviewed_at,
        "resolution_quality_note": row.resolution_quality_note,
        "sla_policy_id": row.sla_policy_id,
        "sla_policy_version": row.sla_policy_version,
        "sla_target_minutes": row.sla_target_minutes,
        "sla_warning_percent": row.sla_warning_percent,
        "sla_started_at": row.sla_started_at,
        "sla_due_at": row.sla_due_at,
        "sla_state": _sla_state(row),
        "version": row.version,
    }


def _append_event(db: Session, row: ReconciliationInvestigation, *, event_type: str,
                  actor_id: int, from_status: Optional[str] = None,
                  to_status: Optional[str] = None, details: Optional[dict] = None) -> None:
    db.add(ReconciliationInvestigationEvent(
        investigation_id=row.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_id,
        details=json.dumps(details, separators=(",", ":"), sort_keys=True) if details else None,
        occurred_at=datetime.now(timezone.utc),
    ))


@router.post("/reconciliation/sla-policies", status_code=status.HTTP_201_CREATED)
def create_reconciliation_sla_policy(
    payload: SLAPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    existing = db.query(ReconciliationSLAPolicy).filter(
        ReconciliationSLAPolicy.severity == payload.severity
    ).with_for_update().all()
    next_version = max((item.version for item in existing), default=0) + 1
    for item in existing:
        if item.is_active:
            item.is_active = False
    policy = ReconciliationSLAPolicy(
        severity=payload.severity, version=next_version,
        target_minutes=payload.target_minutes, warning_percent=payload.warning_percent,
        is_active=True, created_by_id=current_user.id,
    )
    try:
        db.add(policy)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A concurrent SLA policy update occurred; retry.") from exc
    db.refresh(policy)
    return {
        "id": policy.id, "severity": policy.severity, "version": policy.version,
        "target_minutes": policy.target_minutes, "warning_percent": policy.warning_percent,
        "is_active": policy.is_active, "created_by_id": policy.created_by_id,
        "created_at": policy.created_at,
    }


@router.get("/reconciliation/sla-policies", response_model=list[dict])
def list_reconciliation_sla_policies(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    query = db.query(ReconciliationSLAPolicy)
    if active_only:
        query = query.filter(ReconciliationSLAPolicy.is_active.is_(True))
    rows = query.order_by(ReconciliationSLAPolicy.severity, ReconciliationSLAPolicy.version.desc()).all()
    return [{
        "id": row.id, "severity": row.severity, "version": row.version,
        "target_minutes": row.target_minutes, "warning_percent": row.warning_percent,
        "is_active": row.is_active, "created_by_id": row.created_by_id,
        "created_at": row.created_at,
    } for row in rows]


@router.get("/reconciliation/sla-summary", response_model=dict)
def get_reconciliation_sla_summary(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    now = datetime.now(timezone.utc)
    active_statuses = ("OPEN", "ASSIGNED", "IN_REVIEW")
    base = db.query(ReconciliationInvestigation).filter(ReconciliationInvestigation.status.in_(active_statuses))
    total_open = base.count()
    configured = base.filter(ReconciliationInvestigation.sla_due_at.is_not(None)).count()
    overdue = base.filter(ReconciliationInvestigation.sla_due_at < now).count()
    by_severity = dict(db.query(
        ReconciliationInvestigation.severity, func.count(ReconciliationInvestigation.id),
    ).filter(
        ReconciliationInvestigation.status.in_(active_statuses),
        ReconciliationInvestigation.sla_due_at < now,
    ).group_by(ReconciliationInvestigation.severity).all())
    return {
        "open_investigations": total_open,
        "with_sla": configured,
        "without_sla": total_open - configured,
        "overdue": overdue,
        "overdue_by_severity": {key: int(value) for key, value in by_severity.items()},
        "clock_semantics": "Elapsed wall-clock minutes; pause-aware calendars are not enabled.",
    }


@router.post("/reconciliation/investigations", status_code=status.HTTP_201_CREATED)
def create_reconciliation_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    source = db.get(_source_model(payload.source_type), payload.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Reconciliation source record not found.")
    external_key = f"{payload.candidate_type}:{payload.source_type}:{payload.source_id}"
    now = datetime.now(timezone.utc)
    policy = db.query(ReconciliationSLAPolicy).filter(
        ReconciliationSLAPolicy.severity == payload.severity,
        ReconciliationSLAPolicy.is_active.is_(True),
    ).one_or_none()
    existing = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.external_key == external_key
    ).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail={
            "message": "An investigation already exists for this candidate source.",
            "investigation_id": existing.id,
        })
    row = ReconciliationInvestigation(
        external_key=external_key,
        candidate_type=payload.candidate_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        source_reference=payload.source_reference.strip() if payload.source_reference else None,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        severity=payload.severity,
        status="OPEN",
        opened_by_id=current_user.id,
        opened_at=now,
        sla_policy_id=policy.id if policy else None,
        sla_policy_version=policy.version if policy else None,
        sla_target_minutes=policy.target_minutes if policy else None,
        sla_warning_percent=policy.warning_percent if policy else None,
        sla_started_at=now if policy else None,
        sla_due_at=now + timedelta(minutes=policy.target_minutes) if policy else None,
        version=1,
    )
    try:
        db.add(row)
        db.flush()
        _append_event(db, row, event_type="OPENED", actor_id=current_user.id,
                      to_status="OPEN", details={"source_type": row.source_type, "source_id": row.source_id})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An investigation already exists for this candidate source.") from exc
    db.refresh(row)
    return _case_payload(row)


@router.get("/reconciliation/investigations", response_model=dict)
def list_reconciliation_investigations(
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(OPEN|ASSIGNED|IN_REVIEW|RESOLVED|DISMISSED)$"),
    severity: Optional[str] = Query(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"),
    assigned_to_id: Optional[int] = Query(default=None, gt=0),
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(ReconciliationInvestigation)
    if status_filter:
        query = query.filter(ReconciliationInvestigation.status == status_filter)
    if severity:
        query = query.filter(ReconciliationInvestigation.severity == severity)
    if assigned_to_id is not None:
        query = query.filter(ReconciliationInvestigation.assigned_to_id == assigned_to_id)
    total = query.count()
    rows = query.order_by(
        ReconciliationInvestigation.severity.desc(),
        ReconciliationInvestigation.opened_at.desc(),
        ReconciliationInvestigation.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_case_payload(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.patch("/reconciliation/investigations/{investigation_id}/assign")
def assign_reconciliation_investigation(
    investigation_id: int,
    payload: InvestigationAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    row = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.id == investigation_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "Investigation was updated by another user.", "current_version": row.version})
    if row.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Closed investigations cannot be reassigned.")
    if db.get(User, payload.assigned_to_id) is None:
        raise HTTPException(status_code=404, detail="Assignee not found.")
    old_status = row.status
    row.assigned_to_id = payload.assigned_to_id
    if row.status == "OPEN":
        row.status = "ASSIGNED"
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    _append_event(db, row, event_type="ASSIGNED", actor_id=current_user.id,
                  from_status=old_status, to_status=row.status,
                  details={"assigned_to_id": payload.assigned_to_id, "note": payload.note})
    db.commit()
    db.refresh(row)
    return _case_payload(row)


@router.patch("/reconciliation/investigations/{investigation_id}/transition")
def transition_reconciliation_investigation(
    investigation_id: int,
    payload: InvestigationTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.id == investigation_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "Investigation was updated by another user.", "current_version": row.version})
    allowed = {
        "OPEN": {"IN_REVIEW", "DISMISSED"},
        "ASSIGNED": {"IN_REVIEW", "DISMISSED"},
        "IN_REVIEW": {"RESOLVED", "DISMISSED"},
    }
    if payload.to_status not in allowed.get(row.status, set()):
        raise HTTPException(status_code=409, detail=f"Transition from {row.status} to {payload.to_status} is not allowed.")
    if payload.to_status == "RESOLVED" and not payload.resolution:
        raise HTTPException(status_code=422, detail="A resolution note is required to resolve an investigation.")
    if payload.to_status == "DISMISSED" and not (payload.resolution or payload.note):
        raise HTTPException(status_code=422, detail="A reason is required to dismiss an investigation.")
    old_status = row.status
    row.status = payload.to_status
    if payload.resolution:
        row.resolution = payload.resolution.strip()
    elif payload.to_status == "DISMISSED" and payload.note:
        row.resolution = payload.note.strip()
    if payload.root_cause:
        row.root_cause = payload.root_cause.strip()
    if payload.to_status in {"RESOLVED", "DISMISSED"}:
        row.resolved_at = datetime.now(timezone.utc)
        row.closed_by_id = current_user.id
        if payload.to_status == "RESOLVED":
            row.resolution_quality_status = "NOT_REVIEWED"
            row.resolution_quality_reviewed_by_id = None
            row.resolution_quality_reviewed_at = None
            row.resolution_quality_note = None
    else:
        row.resolved_at = None
        row.closed_by_id = None
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    _append_event(db, row, event_type="STATUS_CHANGED", actor_id=current_user.id,
                  from_status=old_status, to_status=row.status,
                  details={"resolution": payload.resolution, "root_cause": payload.root_cause, "note": payload.note})
    db.commit()
    db.refresh(row)
    return _case_payload(row)


@router.get("/reconciliation/investigations/{investigation_id}/events", response_model=list[dict])
def list_reconciliation_investigation_events(
    investigation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(ReconciliationInvestigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    rows = db.query(ReconciliationInvestigationEvent).filter(
        ReconciliationInvestigationEvent.investigation_id == investigation_id
    ).order_by(ReconciliationInvestigationEvent.occurred_at, ReconciliationInvestigationEvent.id).all()
    return [{
        "id": row.id,
        "event_type": row.event_type,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "actor_user_id": row.actor_user_id,
        "details": row.details,
        "occurred_at": row.occurred_at,
    } for row in rows]



@router.patch("/reconciliation/investigations/{investigation_id}/reopen")
def reopen_reconciliation_investigation(
    investigation_id: int,
    payload: InvestigationReopen,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.id == investigation_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "Investigation was updated by another user.", "current_version": row.version})
    if row.status != "RESOLVED":
        raise HTTPException(status_code=409, detail="Only resolved investigations can be reopened.")
    previous_resolution = row.resolution
    previous_root_cause = row.root_cause
    row.status = "IN_REVIEW"
    row.resolved_at = None
    row.closed_by_id = None
    row.reopen_count += 1
    row.resolution_quality_status = "NOT_REVIEWED"
    row.resolution_quality_reviewed_by_id = None
    row.resolution_quality_reviewed_at = None
    row.resolution_quality_note = None
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    _append_event(
        db, row, event_type="REOPENED", actor_id=current_user.id,
        from_status="RESOLVED", to_status="IN_REVIEW",
        details={
            "reason": payload.reason.strip(),
            "previous_resolution": previous_resolution,
            "previous_root_cause": previous_root_cause,
            "reopen_count": row.reopen_count,
        },
    )
    db.commit()
    db.refresh(row)
    return _case_payload(row)


@router.patch("/reconciliation/investigations/{investigation_id}/quality-review")
def review_reconciliation_investigation_closure(
    investigation_id: int,
    payload: InvestigationQualityReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.id == investigation_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "Investigation was updated by another user.", "current_version": row.version})
    if row.status != "RESOLVED":
        raise HTTPException(status_code=409, detail="Only resolved investigations can receive closure-quality review.")
    if row.resolution_quality_status != "NOT_REVIEWED":
        raise HTTPException(status_code=409, detail="This closure has already received a quality decision.")
    if row.closed_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="The investigator who resolved the case cannot review its closure.")
    if payload.decision == "REJECTED" and not (payload.note and payload.note.strip()):
        raise HTTPException(status_code=422, detail="A review note is required when closure quality is rejected.")
    row.resolution_quality_status = payload.decision
    row.resolution_quality_reviewed_by_id = current_user.id
    row.resolution_quality_reviewed_at = datetime.now(timezone.utc)
    row.resolution_quality_note = payload.note.strip() if payload.note else None
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    _append_event(
        db, row, event_type="CLOSURE_QUALITY_REVIEWED", actor_id=current_user.id,
        from_status="RESOLVED", to_status="RESOLVED",
        details={"decision": payload.decision, "note": payload.note},
    )
    db.commit()
    db.refresh(row)
    return _case_payload(row)


@router.get("/reconciliation/investigations/quality-summary", response_model=dict)
def get_reconciliation_investigation_quality_summary(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    total = db.query(func.count(ReconciliationInvestigation.id)).scalar() or 0
    resolved_count = db.query(func.count(ReconciliationInvestigation.id)).filter(
        ReconciliationInvestigation.status == "RESOLVED"
    ).scalar() or 0
    quality_counts = dict(db.query(
        ReconciliationInvestigation.resolution_quality_status,
        func.count(ReconciliationInvestigation.id),
    ).filter(
        ReconciliationInvestigation.status == "RESOLVED"
    ).group_by(ReconciliationInvestigation.resolution_quality_status).all())
    reopened_count = db.query(func.coalesce(func.sum(ReconciliationInvestigation.reopen_count), 0)).scalar() or 0
    cases_reopened = db.query(func.count(ReconciliationInvestigation.id)).filter(
        ReconciliationInvestigation.reopen_count > 0
    ).scalar() or 0
    average_reopens = db.query(func.avg(ReconciliationInvestigation.reopen_count)).scalar()
    return {
        "total_investigations": int(total),
        "resolved_count": int(resolved_count),
        "closure_quality": {
            "not_reviewed": int(quality_counts.get("NOT_REVIEWED", 0)),
            "approved": int(quality_counts.get("APPROVED", 0)),
            "rejected": int(quality_counts.get("REJECTED", 0)),
        },
        "reopened_count": int(reopened_count),
        "cases_reopened": int(cases_reopened),
        "average_reopens_per_case": round(float(average_reopens or 0), 2),
        "limitations": [
            "Quality decisions are explicit human reviews, not automated correctness scores.",
            "This summary is a live aggregate, not a frozen monthly governance snapshot.",
        ],
    }
