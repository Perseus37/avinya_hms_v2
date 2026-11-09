"""Human-owned reconciliation investigation lifecycle.

Source references are polymorphic and deliberately not foreign keys. The source
record remains in its owning procurement table; this case stores a stable source
type/id/reference and never copies patient or bank-account payloads.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import case, cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.domains.identity.models import User, UserStatusEnum
from backend.domains.procurement.models import (
    BankStatementLine,
    ReconciliationInvestigation,
    ReconciliationInvestigationEvent,
    ReconciliationGovernanceReport,
    ReconciliationSLAPolicy,
    SupplierPayment,
    SupplierPaymentRequest,
)

router = APIRouter()

# Investigator-entered root causes are categorical codes, never free text.
ROOT_CAUSE_CATEGORIES = (
    "DUPLICATE_REFERENCE",
    "VENDOR_MISMATCH",
    "AMOUNT_MISMATCH",
    "TIMING_DIFFERENCE",
    "PAYMENT_ALLOCATION_ERROR",
    "MISSING_SUPPORTING_DOCUMENT",
    "BANK_STATEMENT_DATA_ERROR",
    "PROCESS_CONTROL_GAP",
    "OTHER",
)


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

    @field_validator("resolution", "note")
    @classmethod
    def normalize_required_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None

    @field_validator("root_cause")
    @classmethod
    def normalize_root_cause(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"[\s-]+", "_", value.strip().upper())
        if normalized not in ROOT_CAUSE_CATEGORIES:
            raise ValueError("root_cause must be an approved categorical code.")
        return normalized

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
        if closed and closed.tzinfo is None:
            closed = closed.replace(tzinfo=timezone.utc)
        return "CLOSED_ON_TIME" if closed and closed <= due else "CLOSED_LATE"
    if now >= due:
        return "BREACHED"
    started = row.sla_started_at or row.opened_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
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
    external_key = f"{payload.source_type}:{payload.source_id}"
    now = datetime.now(timezone.utc)
    policy = db.query(ReconciliationSLAPolicy).filter(
        ReconciliationSLAPolicy.severity == payload.severity,
        ReconciliationSLAPolicy.is_active.is_(True),
    ).one_or_none()
    existing = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.source_type == payload.source_type,
        ReconciliationInvestigation.source_id == payload.source_id,
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
    assignee = db.get(User, payload.assigned_to_id)
    if assignee is None:
        raise HTTPException(status_code=404, detail="Assignee not found.")
    if assignee.status != UserStatusEnum.ACTIVE:
        raise HTTPException(status_code=409, detail="Only active users can be assigned to reconciliation investigations.")
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
    if payload.to_status == "RESOLVED" and not (payload.resolution and payload.resolution.strip()):
        raise HTTPException(status_code=422, detail="A resolution note is required to resolve an investigation.")
    if payload.to_status == "DISMISSED" and not (
        (payload.resolution and payload.resolution.strip())
        or (payload.note and payload.note.strip())
    ):
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
    before_id: Optional[int] = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(ReconciliationInvestigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    query = db.query(ReconciliationInvestigationEvent).filter(
        ReconciliationInvestigationEvent.investigation_id == investigation_id
    )
    if before_id is not None:
        query = query.filter(ReconciliationInvestigationEvent.id < before_id)
    # Descending IDs provide a stable keyset cursor without loading full history.
    rows = query.order_by(ReconciliationInvestigationEvent.id.desc()).limit(limit).all()
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
    # Preserve prior closure context in the immutable REOPENED event, but clear
    # active closure fields so a later resolution cannot inherit stale data.
    row.resolution = None
    row.root_cause = None
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


@router.get("/reconciliation/dashboard", response_model=dict)
def get_reconciliation_finance_dashboard(
    window_days: int = 30,
    queue_limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Read-only, bounded Finance Manager overview of reconciliation governance."""
    if not 1 <= window_days <= 365:
        raise HTTPException(status_code=422, detail="window_days must be between 1 and 365.")
    if not 1 <= queue_limit <= 50:
        raise HTTPException(status_code=422, detail="queue_limit must be between 1 and 50.")

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    active_statuses = ("OPEN", "ASSIGNED", "IN_REVIEW")
    cases = db.query(ReconciliationInvestigation)

    total = cases.count()
    active = cases.filter(ReconciliationInvestigation.status.in_(active_statuses))
    active_count = active.count()
    overdue_count = active.filter(
        ReconciliationInvestigation.sla_due_at.is_not(None),
        ReconciliationInvestigation.sla_due_at < now,
    ).count()
    due_soon_count = active.filter(
        ReconciliationInvestigation.sla_due_at.is_not(None),
        ReconciliationInvestigation.sla_due_at >= now,
        ReconciliationInvestigation.sla_due_at <= now + timedelta(hours=24),
    ).count()
    without_sla_count = active.filter(ReconciliationInvestigation.sla_due_at.is_(None)).count()

    status_counts = dict(db.query(
        ReconciliationInvestigation.status, func.count(ReconciliationInvestigation.id)
    ).group_by(ReconciliationInvestigation.status).all())
    severity_counts = dict(db.query(
        ReconciliationInvestigation.severity, func.count(ReconciliationInvestigation.id)
    ).filter(
        ReconciliationInvestigation.status.in_(active_statuses)
    ).group_by(ReconciliationInvestigation.severity).all())

    quality_counts = dict(db.query(
        ReconciliationInvestigation.resolution_quality_status,
        func.count(ReconciliationInvestigation.id),
    ).filter(
        ReconciliationInvestigation.status == "RESOLVED"
    ).group_by(ReconciliationInvestigation.resolution_quality_status).all())
    reopened_cases = cases.filter(ReconciliationInvestigation.reopen_count > 0).count()
    total_reopens = db.query(
        func.coalesce(func.sum(ReconciliationInvestigation.reopen_count), 0)
    ).scalar() or 0

    opened_in_window = cases.filter(ReconciliationInvestigation.opened_at >= window_start).count()
    resolved_event_filter = (
        ReconciliationInvestigationEvent.event_type == "STATUS_CHANGED",
        ReconciliationInvestigationEvent.to_status == "RESOLVED",
        ReconciliationInvestigationEvent.occurred_at >= window_start,
        ReconciliationInvestigationEvent.occurred_at <= now,
    )
    resolved_in_window = db.query(
        func.count(ReconciliationInvestigationEvent.id)
    ).filter(*resolved_event_filter).scalar() or 0

    if db.bind.dialect.name == "postgresql":
        recorded_root_cause = func.jsonb_extract_path_text(
            cast(ReconciliationInvestigationEvent.details, JSONB), "root_cause"
        )
    else:
        recorded_root_cause = func.json_extract(
            ReconciliationInvestigationEvent.details, "$.root_cause"
        )
    normalized_root_cause = func.upper(func.trim(recorded_root_cause))
    root_causes = db.query(
        normalized_root_cause.label("root_cause"),
        func.count(func.distinct(
            ReconciliationInvestigationEvent.investigation_id
        )).label("resolved_cases"),
    ).filter(
        *resolved_event_filter,
        normalized_root_cause.in_(ROOT_CAUSE_CATEGORIES),
    ).group_by(
        normalized_root_cause
    ).order_by(
        func.count(func.distinct(ReconciliationInvestigationEvent.investigation_id)).desc(),
        normalized_root_cause.asc(),
    ).limit(10).all()

    age_buckets = {
        "under_24_hours": active.filter(
            ReconciliationInvestigation.opened_at >= now - timedelta(hours=24)
        ).count(),
        "1_to_7_days": active.filter(
            ReconciliationInvestigation.opened_at < now - timedelta(hours=24),
            ReconciliationInvestigation.opened_at >= now - timedelta(days=7),
        ).count(),
        "8_to_30_days": active.filter(
            ReconciliationInvestigation.opened_at < now - timedelta(days=7),
            ReconciliationInvestigation.opened_at >= now - timedelta(days=30),
        ).count(),
        "over_30_days": active.filter(
            ReconciliationInvestigation.opened_at < now - timedelta(days=30)
        ).count(),
    }

    queue_rows = active.order_by(
        ReconciliationInvestigation.sla_due_at.is_(None),
        ReconciliationInvestigation.sla_due_at.asc(),
        ReconciliationInvestigation.id.asc(),
    ).limit(queue_limit).all()

    return {
        "generated_at": now,
        "window_days": window_days,
        "overview": {
            "total_investigations": total,
            "active_investigations": active_count,
            "overdue": overdue_count,
            "due_within_24_hours": due_soon_count,
            "active_without_sla": without_sla_count,
        },
        "active_by_severity": {
            severity: int(severity_counts.get(severity, 0))
            for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        },
        "by_status": {
            status_name: int(status_counts.get(status_name, 0))
            for status_name in ("OPEN", "ASSIGNED", "IN_REVIEW", "RESOLVED", "DISMISSED")
        },
        "closure_quality": {
            "awaiting_review": int(quality_counts.get("NOT_REVIEWED", 0)),
            "approved": int(quality_counts.get("APPROVED", 0)),
            "rejected": int(quality_counts.get("REJECTED", 0)),
        },
        "reopening": {
            "cases_reopened": reopened_cases,
            "total_reopens": int(total_reopens),
        },
        "active_case_age": age_buckets,
        "period_activity": {
            "opened": opened_in_window,
            "resolved": resolved_in_window,
            "root_causes": [
                {"root_cause": cause, "resolved_cases": int(count)}
                for cause, count in root_causes
            ],
        },
        "priority_queue": [
            {
                "id": row.id,
                "severity": row.severity,
                "status": row.status,
                "assigned_to_id": row.assigned_to_id,
                "opened_at": row.opened_at,
                "sla_due_at": row.sla_due_at,
                "sla_state": _sla_state(row),
            }
            for row in queue_rows
        ],
        "limitations": [
            "This is a live tenant-local aggregate, not a frozen monthly governance report.",
            "SLA calculations use elapsed wall-clock time; pause-aware business calendars are not enabled.",
            "The priority queue intentionally excludes investigation narratives and source financial details.",
        ],
    }


@router.get("/reconciliation/recurrence-summary", response_model=dict)
def get_reconciliation_recurrence_summary(
    window_days: int = 90,
    min_occurrences: int = 2,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Report repeated exception classes and recorded root-cause labels, without inferring causality."""
    if not 1 <= window_days <= 365:
        raise HTTPException(status_code=422, detail="window_days must be between 1 and 365.")
    if not 2 <= min_occurrences <= 100:
        raise HTTPException(status_code=422, detail="min_occurrences must be between 2 and 100.")
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50.")

    now = datetime.now(timezone.utc)
    opened_since = now - timedelta(days=window_days)
    resolved_since = now - timedelta(days=window_days)

    pattern_rows = db.query(
        ReconciliationInvestigation.candidate_type,
        ReconciliationInvestigation.source_type,
        func.count(ReconciliationInvestigation.id).label("case_count"),
        func.count(func.distinct(ReconciliationInvestigation.source_id)).label("distinct_sources"),
        func.sum(case((ReconciliationInvestigation.severity == "CRITICAL", 1), else_=0)).label("critical_count"),
        func.sum(case((ReconciliationInvestigation.severity == "HIGH", 1), else_=0)).label("high_count"),
        func.sum(ReconciliationInvestigation.reopen_count).label("reopen_count"),
    ).filter(
        ReconciliationInvestigation.opened_at >= opened_since,
    ).group_by(
        ReconciliationInvestigation.candidate_type,
        ReconciliationInvestigation.source_type,
    ).having(
        func.count(ReconciliationInvestigation.id) >= min_occurrences,
    ).order_by(
        func.count(ReconciliationInvestigation.id).desc(),
        ReconciliationInvestigation.candidate_type.asc(),
        ReconciliationInvestigation.source_type.asc(),
    ).limit(limit).all()

    normalized_root_cause = func.upper(func.trim(ReconciliationInvestigation.root_cause))
    root_cause_rows = db.query(
        normalized_root_cause.label("root_cause"),
        func.count(ReconciliationInvestigation.id).label("case_count"),
        func.count(func.distinct(ReconciliationInvestigation.candidate_type)).label("exception_types"),
        func.sum(ReconciliationInvestigation.reopen_count).label("reopen_count"),
        func.sum(case((ReconciliationInvestigation.resolution_quality_status == "REJECTED", 1), else_=0)).label("rejected_reviews"),
    ).filter(
        ReconciliationInvestigation.status == "RESOLVED",
        normalized_root_cause.in_(ROOT_CAUSE_CATEGORIES),
        ReconciliationInvestigation.resolved_at >= resolved_since,
    ).group_by(
        normalized_root_cause,
    ).having(
        func.count(ReconciliationInvestigation.id) >= min_occurrences,
    ).order_by(
        func.count(ReconciliationInvestigation.id).desc(),
        normalized_root_cause.asc(),
    ).limit(limit).all()

    return {
        "generated_at": now,
        "window_days": window_days,
        "minimum_occurrences": min_occurrences,
        "repeated_exception_patterns": [
            {
                "candidate_type": row.candidate_type,
                "source_type": row.source_type,
                "investigations": int(row.case_count or 0),
                "distinct_sources": int(row.distinct_sources or 0),
                "critical_cases": int(row.critical_count or 0),
                "high_cases": int(row.high_count or 0),
                "reopens": int(row.reopen_count or 0),
            }
            for row in pattern_rows
        ],
        "recurring_recorded_root_causes": [
            {
                "root_cause": row.root_cause,
                "resolved_cases": int(row.case_count or 0),
                "exception_types": int(row.exception_types or 0),
                "reopens": int(row.reopen_count or 0),
                "rejected_quality_reviews": int(row.rejected_reviews or 0),
            }
            for row in root_cause_rows
        ],
        "interpretation_limits": [
            "Repeated exception patterns group human-created investigations by candidate type and source type; they do not prove a shared underlying cause.",
            "Root-cause recurrence groups normalized labels entered by investigators; labels are not independently verified causal findings.",
            "Only resolved cases with a recorded root-cause label contribute to root-cause recurrence.",
            "Counts are live tenant-local aggregates, not immutable monthly snapshots.",
        ],
    }


class GovernanceReportGenerate(BaseModel):
    report_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


def _governance_report_payload(db: Session, *, period_start: datetime,
                               period_end: datetime, generated_at: datetime) -> dict:
    """Build a bounded aggregate-only monthly snapshot; never select narrative/source identifiers."""
    opened = db.query(func.count(ReconciliationInvestigation.id)).filter(
        ReconciliationInvestigation.opened_at >= period_start,
        ReconciliationInvestigation.opened_at < period_end,
    ).scalar() or 0
    resolved_event_filter = (
        ReconciliationInvestigationEvent.event_type == "STATUS_CHANGED",
        ReconciliationInvestigationEvent.to_status == "RESOLVED",
        ReconciliationInvestigationEvent.occurred_at >= period_start,
        ReconciliationInvestigationEvent.occurred_at < period_end,
    )
    resolved = db.query(func.count(ReconciliationInvestigationEvent.id)).filter(
        *resolved_event_filter
    ).scalar() or 0
    reopened = db.query(func.count(ReconciliationInvestigationEvent.id)).filter(
        ReconciliationInvestigationEvent.event_type == "REOPENED",
        ReconciliationInvestigationEvent.occurred_at >= period_start,
        ReconciliationInvestigationEvent.occurred_at < period_end,
    ).scalar() or 0

    # A case may be reopened after a resolution. Its mutable current state must
    # not erase the historical resolution activity captured by the event ledger.
    resolved_case_ids = db.query(
        ReconciliationInvestigationEvent.investigation_id
    ).filter(*resolved_event_filter).distinct().subquery()
    quality_rows = db.query(
        ReconciliationInvestigation.resolution_quality_status,
        func.count(ReconciliationInvestigation.id),
    ).filter(
        ReconciliationInvestigation.id.in_(
            db.query(resolved_case_ids.c.investigation_id)
        )
    ).group_by(ReconciliationInvestigation.resolution_quality_status).all()
    quality = {status: int(count or 0) for status, count in quality_rows}

    sla_rows = db.query(
        func.sum(case((
            ReconciliationInvestigationEvent.occurred_at <= ReconciliationInvestigation.sla_due_at, 1
        ), else_=0)),
        func.sum(case((
            ReconciliationInvestigationEvent.occurred_at > ReconciliationInvestigation.sla_due_at, 1
        ), else_=0)),
    ).join(
        ReconciliationInvestigation,
        ReconciliationInvestigation.id == ReconciliationInvestigationEvent.investigation_id,
    ).filter(
        *resolved_event_filter,
        ReconciliationInvestigation.sla_due_at.is_not(None),
    ).one()
    resolved_with_sla = db.query(func.count(ReconciliationInvestigationEvent.id)).join(
        ReconciliationInvestigation,
        ReconciliationInvestigation.id == ReconciliationInvestigationEvent.investigation_id,
    ).filter(
        *resolved_event_filter,
        ReconciliationInvestigation.sla_due_at.is_not(None),
    ).scalar() or 0

    pattern_rows = db.query(
        ReconciliationInvestigation.candidate_type,
        ReconciliationInvestigation.source_type,
        func.count(ReconciliationInvestigation.id).label("case_count"),
    ).filter(
        ReconciliationInvestigation.opened_at >= period_start,
        ReconciliationInvestigation.opened_at < period_end,
    ).group_by(
        ReconciliationInvestigation.candidate_type,
        ReconciliationInvestigation.source_type,
    ).having(func.count(ReconciliationInvestigation.id) >= 2).order_by(
        func.count(ReconciliationInvestigation.id).desc(),
        ReconciliationInvestigation.candidate_type.asc(),
        ReconciliationInvestigation.source_type.asc(),
    ).limit(25).all()

    if db.get_bind().dialect.name == "postgresql":
        recorded_root_cause = func.jsonb_extract_path_text(
            cast(ReconciliationInvestigationEvent.details, JSONB), "root_cause"
        )
    else:
        recorded_root_cause = func.json_extract(
            ReconciliationInvestigationEvent.details, "$.root_cause"
        )
    normalized_root_cause = func.upper(func.trim(recorded_root_cause))
    cause_rows = db.query(
        normalized_root_cause.label("root_cause"),
        func.count(func.distinct(ReconciliationInvestigationEvent.investigation_id)).label("case_count"),
    ).filter(
        *resolved_event_filter,
        normalized_root_cause.in_(ROOT_CAUSE_CATEGORIES),
    ).group_by(normalized_root_cause).having(
        func.count(func.distinct(ReconciliationInvestigationEvent.investigation_id)) >= 2
    ).order_by(
        func.count(func.distinct(ReconciliationInvestigationEvent.investigation_id)).desc(),
        normalized_root_cause.asc(),
    ).limit(25).all()

    active_filter = ReconciliationInvestigation.status.in_(("OPEN", "ASSIGNED", "IN_REVIEW"))
    active_count = db.query(func.count(ReconciliationInvestigation.id)).filter(active_filter).scalar() or 0
    severity_rows = db.query(
        ReconciliationInvestigation.severity, func.count(ReconciliationInvestigation.id)
    ).filter(active_filter).group_by(ReconciliationInvestigation.severity).all()
    overdue = db.query(func.count(ReconciliationInvestigation.id)).filter(
        active_filter, ReconciliationInvestigation.sla_due_at.is_not(None),
        ReconciliationInvestigation.sla_due_at < generated_at,
    ).scalar() or 0
    missing_sla = db.query(func.count(ReconciliationInvestigation.id)).filter(
        active_filter, ReconciliationInvestigation.sla_due_at.is_(None),
    ).scalar() or 0

    return {
        "schema_version": 1,
        "report_month": period_start.strftime("%Y-%m"),
        "period": {"start_utc": period_start.isoformat(), "end_utc_exclusive": period_end.isoformat()},
        "generated_at": generated_at.isoformat(),
        "activity": {"opened": int(opened), "resolved": int(resolved), "reopened_events": int(reopened)},
        "closure_quality": {
            "not_reviewed": int(quality.get("NOT_REVIEWED", 0)),
            "approved": int(quality.get("APPROVED", 0)),
            "rejected": int(quality.get("REJECTED", 0)),
        },
        "sla": {
            "resolved_with_sla": int(resolved_with_sla),
            "closed_on_time": int(sla_rows[0] or 0),
            "closed_late": int(sla_rows[1] or 0),
            "resolved_without_sla": int(resolved - resolved_with_sla),
        },
        "recurring_exception_patterns": [
            {"candidate_type": row.candidate_type, "source_type": row.source_type,
             "investigations": int(row.case_count or 0)} for row in pattern_rows
        ],
        "recurring_recorded_root_causes": [
            {"root_cause": row.root_cause, "resolved_cases": int(row.case_count or 0)}
            for row in cause_rows
        ],
        "backlog_at_generation": {
            "active": int(active_count),
            "active_by_severity": {severity: int(count or 0) for severity, count in severity_rows},
            "overdue": int(overdue),
            "missing_sla": int(missing_sla),
        },
        "interpretation_limits": [
            "Period activity uses UTC timestamps and half-open calendar-month boundaries.",
            "Closure quality is the state observed at report generation, not necessarily at closure time.",
            "Backlog is a point-in-time snapshot at generation, not a reconstructed month-end backlog.",
            "SLA outcomes use stored elapsed-time deadlines and do not apply business calendars or pause windows.",
            "Recurring patterns and root-cause labels are human-recorded indicators, not proof of shared or verified causes.",
        ],
    }


def _governance_report_metadata(row: ReconciliationGovernanceReport) -> dict:
    return {
        "id": row.id,
        "report_month": row.report_month,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "generated_at": row.generated_at,
        "generated_by_id": row.generated_by_id,
        "schema_version": row.schema_version,
        "payload_sha256": row.payload_sha256,
    }


@router.post("/reconciliation/governance-reports", status_code=status.HTTP_201_CREATED)
def generate_reconciliation_governance_report(
    payload: GovernanceReportGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    try:
        period_start = datetime.strptime(payload.report_month, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="report_month must use YYYY-MM.")
    next_month_year = period_start.year + (1 if period_start.month == 12 else 0)
    next_month = 1 if period_start.month == 12 else period_start.month + 1
    period_end = period_start.replace(year=next_month_year, month=next_month)
    now = datetime.now(timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start >= current_month_start:
        raise HTTPException(status_code=422, detail="Only completed UTC calendar months can be reported.")
    if db.query(ReconciliationGovernanceReport.id).filter(
        ReconciliationGovernanceReport.report_month == payload.report_month
    ).first():
        raise HTTPException(status_code=409, detail="A governance report already exists for this month.")
    snapshot = _governance_report_payload(
        db, period_start=period_start, period_end=period_end, generated_at=now
    )
    canonical = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    row = ReconciliationGovernanceReport(
        report_month=payload.report_month,
        period_start=period_start,
        period_end=period_end,
        generated_at=now,
        generated_by_id=current_user.id,
        schema_version=1,
        payload=canonical,
        payload_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A governance report already exists for this month.")
    db.refresh(row)
    return {**_governance_report_metadata(row), "payload": snapshot}


@router.get("/reconciliation/governance-reports")
def list_reconciliation_governance_reports(
    before_id: Optional[int] = None,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:read")),
):
    if limit < 1 or limit > 100 or (before_id is not None and before_id < 1):
        raise HTTPException(status_code=422, detail="Invalid governance report pagination.")
    query = db.query(ReconciliationGovernanceReport)
    if before_id is not None:
        query = query.filter(ReconciliationGovernanceReport.id < before_id)
    rows = query.order_by(ReconciliationGovernanceReport.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [_governance_report_metadata(row) for row in rows],
        "next_before_id": rows[-1].id if has_more and rows else None,
    }


@router.get("/reconciliation/governance-reports/{report_id}")
def get_reconciliation_governance_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:read")),
):
    row = db.query(ReconciliationGovernanceReport).filter(
        ReconciliationGovernanceReport.id == report_id
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Governance report not found.")
    return {**_governance_report_metadata(row), "payload": json.loads(row.payload)}
