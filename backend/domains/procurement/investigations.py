"""Human-owned reconciliation investigation lifecycle.

Source references are polymorphic and deliberately not foreign keys. The source
record remains in its owning procurement table; this case stores a stable source
type/id/reference and never copies patient or bank-account payloads.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.domains.identity.models import User
from backend.domains.procurement.models import (
    BankStatementLine,
    ReconciliationInvestigation,
    ReconciliationInvestigationEvent,
    SupplierPayment,
    SupplierPaymentRequest,
)

router = APIRouter()


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


def _source_model(source_type: str):
    return {
        "BANK_STATEMENT_LINE": BankStatementLine,
        "SUPPLIER_PAYMENT": SupplierPayment,
        "SUPPLIER_PAYMENT_REQUEST": SupplierPaymentRequest,
    }[source_type]


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
        version=1,
    )
    db.add(row)
    db.flush()
    _append_event(db, row, event_type="OPENED", actor_id=current_user.id,
                  to_status="OPEN", details={"source_type": row.source_type, "source_id": row.source_id})
    db.commit()
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
    if payload.root_cause:
        row.root_cause = payload.root_cause.strip()
    if payload.to_status in {"RESOLVED", "DISMISSED"}:
        row.resolved_at = datetime.now(timezone.utc)
    else:
        row.resolved_at = None
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
