"""Recipient-scoped read surface for reconciliation in-app notifications.

The outbox payload is intentionally never returned to clients. Only a small,
validated allow-list of operational metadata is exposed to the authenticated
recipient. No worker or external provider is invoked by these routes.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.identity.models import User
from backend.domains.procurement.models import ReconciliationNotificationOutbox

router = APIRouter()


def _notification_view(row: ReconciliationNotificationOutbox) -> dict:
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        payload = {}
    severity = payload.get("severity")
    if severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        severity = None
    event_type = row.event_type if row.event_type in {"SLA_WARNING", "SLA_BREACHED"} else "RECONCILIATION_UPDATE"
    return {
        "id": row.id,
        "investigation_id": row.investigation_id,
        "event_type": event_type,
        "severity": severity,
        "created_at": row.created_at,
        "read_at": row.read_at,
        "is_read": row.read_at is not None,
    }


@router.get("/reconciliation/notifications/me")
def list_my_reconciliation_notifications(
    unread_only: bool = False,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    base = db.query(ReconciliationNotificationOutbox).filter(
        ReconciliationNotificationOutbox.recipient_user_id == actor.id,
        ReconciliationNotificationOutbox.channel == "IN_APP",
    )
    unread_count = base.filter(ReconciliationNotificationOutbox.read_at.is_(None)).count()
    query = base
    if unread_only:
        query = query.filter(ReconciliationNotificationOutbox.read_at.is_(None))
    if before_id is not None:
        query = query.filter(ReconciliationNotificationOutbox.id < before_id)
    rows = query.order_by(
        ReconciliationNotificationOutbox.id.desc()
    ).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [_notification_view(row) for row in rows],
        "unread_count": unread_count,
        "next_before_id": rows[-1].id if has_more and rows else None,
        "limit": limit,
    }


@router.patch("/reconciliation/notifications/me/{notification_id}/read")
def mark_my_reconciliation_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    row = db.query(ReconciliationNotificationOutbox).filter(
        ReconciliationNotificationOutbox.id == notification_id,
        ReconciliationNotificationOutbox.recipient_user_id == actor.id,
        ReconciliationNotificationOutbox.channel == "IN_APP",
    ).with_for_update().one_or_none()
    if row is None:
        # Do not reveal whether another user's notification ID exists.
        raise HTTPException(status_code=404, detail="Notification not found.")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
    return _notification_view(row)
