"""Configuration APIs for reconciliation escalation and personal notification preferences.

This stage stores configuration only. It does not evaluate SLA triggers, create outbox
messages, or send notifications. External channels remain unavailable until adapters
and their operational controls are implemented.
"""
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, get_current_user
from backend.domains.identity.models import Role, User
from backend.domains.procurement.models import (
    ReconciliationEscalationPolicy,
    ReconciliationNotificationPreference,
    ReconciliationNotificationConfigEvent,
)

router = APIRouter()


class EscalationPolicyCreate(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    trigger: Literal["WARNING", "BREACHED"]
    enabled: bool = False
    delay_minutes: int = Field(default=0, ge=0, le=525600)
    recipient_role_ids: list[int] = Field(default_factory=list, max_length=30)
    channels: list[Literal["IN_APP", "EMAIL", "SMS", "PUSH"]] = Field(default_factory=lambda: ["IN_APP"], min_length=1, max_length=1)

    @model_validator(mode="after")
    def validate_channels(self):
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("channels must be unique")
        if any(channel != "IN_APP" for channel in self.channels):
            raise ValueError("External notification channels are not enabled in this release stage.")
        if len(set(self.recipient_role_ids)) != len(self.recipient_role_ids):
            raise ValueError("recipient_role_ids must be unique")
        return self


class PreferenceUpdate(BaseModel):
    event_type: Literal["SLA_WARNING", "SLA_BREACHED"]
    channel: Literal["IN_APP", "EMAIL", "SMS", "PUSH"]
    enabled: bool


def _policy_payload(row):
    return {
        "id": row.id, "severity": row.severity, "trigger": row.trigger,
        "version": row.version, "enabled": row.enabled,
        "delay_minutes": row.delay_minutes,
        "recipient_role_ids": json.loads(row.recipient_role_ids),
        "channels": json.loads(row.channels), "is_active": row.is_active,
        "created_by_id": row.created_by_id, "created_at": row.created_at,
    }


@router.post("/reconciliation/escalation-policies", status_code=status.HTTP_201_CREATED)
def create_escalation_policy(
    payload: EscalationPolicyCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("finance:approve")),
):
    role_ids = sorted(payload.recipient_role_ids)
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []
    if len(roles) != len(role_ids):
        raise HTTPException(status_code=422, detail="One or more recipient roles do not exist in this tenant.")
    rows = db.query(ReconciliationEscalationPolicy).filter(
        ReconciliationEscalationPolicy.severity == payload.severity,
        ReconciliationEscalationPolicy.trigger == payload.trigger,
    ).with_for_update().all()
    version = max((row.version for row in rows), default=0) + 1
    for row in rows:
        if row.is_active:
            row.is_active = False
    policy = ReconciliationEscalationPolicy(
        severity=payload.severity, trigger=payload.trigger, version=version,
        enabled=payload.enabled, delay_minutes=payload.delay_minutes,
        recipient_role_ids=json.dumps(role_ids),
        channels=json.dumps(payload.channels), is_active=True,
        created_by_id=actor.id,
    )
    db.add(policy)
    try:
        db.flush()
        db.add(ReconciliationNotificationConfigEvent(
            actor_user_id=actor.id, event_type="ESCALATION_POLICY_CREATED",
            object_type="ESCALATION_POLICY", object_id=policy.id,
            details=json.dumps({"severity": payload.severity, "trigger": payload.trigger,
                                "version": version, "enabled": payload.enabled,
                                "role_ids": role_ids, "channels": payload.channels},
                               separators=(",", ":"), sort_keys=True),
            occurred_at=datetime.now(timezone.utc),
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A concurrent escalation policy update occurred; retry.") from exc
    db.refresh(policy)
    return _policy_payload(policy)


@router.get("/reconciliation/escalation-policies", response_model=list[dict])
def list_escalation_policies(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    query = db.query(ReconciliationEscalationPolicy)
    if active_only:
        query = query.filter(ReconciliationEscalationPolicy.is_active.is_(True))
    rows = query.order_by(ReconciliationEscalationPolicy.severity,
                          ReconciliationEscalationPolicy.trigger,
                          ReconciliationEscalationPolicy.version.desc()).all()
    return [_policy_payload(row) for row in rows]


@router.get("/reconciliation/notification-preferences/me", response_model=list[dict])
def get_my_notification_preferences(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    rows = db.query(ReconciliationNotificationPreference).filter(
        ReconciliationNotificationPreference.user_id == actor.id
    ).order_by(ReconciliationNotificationPreference.event_type,
               ReconciliationNotificationPreference.channel).all()
    stored = {(row.event_type, row.channel): row.enabled for row in rows}
    result = []
    for event_type in ("SLA_WARNING", "SLA_BREACHED"):
        for channel in ("IN_APP", "EMAIL", "SMS", "PUSH"):
            result.append({
                "event_type": event_type, "channel": channel,
                "enabled": stored.get((event_type, channel), channel == "IN_APP"),
                "configured": (event_type, channel) in stored,
                "available": channel == "IN_APP",
            })
    return result


@router.put("/reconciliation/notification-preferences/me", response_model=dict)
def update_my_notification_preferences(
    payload: list[PreferenceUpdate],
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if len(payload) > 8 or len({(item.event_type, item.channel) for item in payload}) != len(payload):
        raise HTTPException(status_code=422, detail="Provide at most one setting per event and channel.")
    if any(item.channel != "IN_APP" and item.enabled for item in payload):
        raise HTTPException(status_code=422, detail="External notification channels are not enabled in this release stage.")
    changed = []
    now = datetime.now(timezone.utc)
    for item in payload:
        row = db.query(ReconciliationNotificationPreference).filter_by(
            user_id=actor.id, event_type=item.event_type, channel=item.channel
        ).with_for_update().one_or_none()
        if row is None:
            row = ReconciliationNotificationPreference(
                user_id=actor.id, event_type=item.event_type, channel=item.channel,
                enabled=item.enabled, updated_at=now, updated_by_id=actor.id,
            )
            db.add(row)
        else:
            row.enabled = item.enabled
            row.updated_at = now
            row.updated_by_id = actor.id
        changed.append({"event_type": item.event_type, "channel": item.channel,
                        "enabled": item.enabled})
    if changed:
        db.add(ReconciliationNotificationConfigEvent(
            actor_user_id=actor.id, subject_user_id=actor.id,
            event_type="NOTIFICATION_PREFERENCES_UPDATED",
            object_type="USER_PREFERENCES", object_id=actor.id,
            details=json.dumps({"changes": changed}, separators=(",", ":"), sort_keys=True),
            occurred_at=now,
        ))
    db.commit()
    return {"updated": len(changed), "preferences": changed}
