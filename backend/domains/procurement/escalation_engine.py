"""Idempotent evaluator for reconciliation SLA escalation intents.

This module only writes tenant-local IN_APP intents to the durable outbox.
It performs no provider calls and is invoked by trusted application/worker code.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domains.identity.models import User, UserRole, UserStatusEnum
from backend.domains.procurement.models import (
    ReconciliationEscalationPolicy,
    ReconciliationInvestigation,
    ReconciliationNotificationOutbox,
    ReconciliationNotificationPreference,
)


OPEN_STATUSES = ("OPEN", "ASSIGNED", "IN_REVIEW")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _trigger_time(case: ReconciliationInvestigation, trigger: str) -> datetime | None:
    if case.sla_started_at is None or case.sla_due_at is None:
        return None
    started = _utc(case.sla_started_at)
    due = _utc(case.sla_due_at)
    if due <= started:
        return None
    if trigger == "BREACHED":
        return due
    if trigger == "WARNING" and case.sla_warning_percent:
        elapsed = (due - started).total_seconds() * case.sla_warning_percent / 100
        return started + timedelta(seconds=elapsed)
    return None


def evaluate_reconciliation_escalations(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 500,
    after_case_id: int = 0,
) -> dict:
    """Queue eligible in-app escalation intents; caller owns transaction commit.

    Idempotency is enforced by a database unique key, so repeated or concurrent
    evaluations cannot create duplicate intents for the same case/policy/recipient.
    """
    if batch_size < 1 or batch_size > 5000:
        raise ValueError("batch_size must be between 1 and 5000")
    if after_case_id < 0:
        raise ValueError("after_case_id must be zero or greater")
    evaluated_at = _utc(now or datetime.now(timezone.utc))

    policies = db.query(ReconciliationEscalationPolicy).filter(
        ReconciliationEscalationPolicy.is_active.is_(True),
        ReconciliationEscalationPolicy.enabled.is_(True),
    ).all()
    policies_by_key = {}
    for policy in policies:
        try:
            channels = json.loads(policy.channels)
            role_ids = json.loads(policy.recipient_role_ids)
        except (TypeError, ValueError):
            continue
        # Fail closed if configuration has been corrupted or contains a future channel.
        if channels != ["IN_APP"] or not isinstance(role_ids, list):
            continue
        normalized_roles = sorted({int(role_id) for role_id in role_ids if str(role_id).isdecimal()})
        if not normalized_roles:
            continue
        policies_by_key[(policy.severity, policy.trigger)] = (policy, normalized_roles)

    cases = db.query(ReconciliationInvestigation).filter(
        ReconciliationInvestigation.status.in_(OPEN_STATUSES),
        ReconciliationInvestigation.sla_started_at.is_not(None),
        ReconciliationInvestigation.sla_due_at.is_not(None),
    ).filter(
        ReconciliationInvestigation.id > after_case_id
    ).order_by(ReconciliationInvestigation.id.asc()).limit(batch_size).all()

    counts = {
        "cases_scanned": len(cases),
        "next_after_case_id": cases[-1].id if cases else after_case_id,
        "eligible_triggers": 0,
        "recipients_considered": 0,
        "created": 0,
        "duplicates": 0,
        "no_active_recipients": 0,
        "opted_out": 0,
    }

    for case in cases:
        for trigger in ("WARNING", "BREACHED"):
            configured = policies_by_key.get((case.severity, trigger))
            if not configured:
                continue
            policy, role_ids = configured
            trigger_at = _trigger_time(case, trigger)
            if trigger_at is None:
                continue
            available_at = trigger_at + timedelta(minutes=policy.delay_minutes)
            if evaluated_at < available_at:
                continue
            if trigger == "WARNING" and evaluated_at >= _utc(case.sla_due_at):
                # A late evaluator should not emit a stale warning after breach.
                continue

            counts["eligible_triggers"] += 1
            recipients = db.query(User).join(
                UserRole, UserRole.user_id == User.id
            ).filter(
                UserRole.role_id.in_(role_ids),
                User.status == UserStatusEnum.ACTIVE,
            ).distinct().all()
            if not recipients:
                counts["no_active_recipients"] += 1
                continue

            event_type = "SLA_WARNING" if trigger == "WARNING" else "SLA_BREACHED"
            for recipient in recipients:
                counts["recipients_considered"] += 1
                preference = db.query(ReconciliationNotificationPreference).filter_by(
                    user_id=recipient.id,
                    event_type=event_type,
                    channel="IN_APP",
                ).one_or_none()
                if preference is not None and not preference.enabled:
                    counts["opted_out"] += 1
                    continue

                key = (
                    f"recon:{case.id}:{event_type}:policy:{policy.id}:"
                    f"v{policy.version}:user:{recipient.id}:IN_APP"
                )
                payload = json.dumps(
                    {
                        "investigation_id": case.id,
                        "event_type": event_type,
                        "severity": case.severity,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                try:
                    with db.begin_nested():
                        db.add(ReconciliationNotificationOutbox(
                            idempotency_key=key,
                            investigation_id=case.id,
                            policy_id=policy.id,
                            policy_version=policy.version,
                            recipient_user_id=recipient.id,
                            event_type=event_type,
                            channel="IN_APP",
                            status="PENDING",
                            payload=payload,
                            available_at=available_at,
                            created_at=evaluated_at,
                        ))
                        db.flush()
                    counts["created"] += 1
                except IntegrityError:
                    counts["duplicates"] += 1

    db.flush()
    return counts
