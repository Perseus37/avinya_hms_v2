from datetime import datetime, timedelta, timezone
import json

from sqlalchemy.orm import Session


def test_reconciliation_escalation_evaluator_is_idempotent_and_honors_opt_out(
    multi_tenant_env,
):
    from backend.domains.identity.models import Role, User, UserRole
    from backend.domains.procurement.escalation_engine import evaluate_reconciliation_escalations
    from backend.domains.procurement.models import (
        ReconciliationEscalationPolicy,
        ReconciliationInvestigation,
        ReconciliationNotificationOutbox,
        ReconciliationNotificationPreference,
        ReconciliationSLAPolicy,
    )

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        recipient = db.query(User).filter(User.email == "admin@default.com").one()
        role = Role(code="RECON-ESCALATION-TEST", name="Reconciliation Escalation Test")
        db.add(role)
        db.flush()
        db.add(UserRole(user_id=recipient.id, role_id=role.id))

        sla_policy = ReconciliationSLAPolicy(
            severity="HIGH", version=91, target_minutes=60, warning_percent=80,
            is_active=False, created_by_id=recipient.id,
        )
        db.add(sla_policy)
        db.flush()
        escalation = ReconciliationEscalationPolicy(
            severity="HIGH", trigger="BREACHED", version=1, enabled=True,
            delay_minutes=0, recipient_role_ids=json.dumps([role.id]),
            channels='["IN_APP"]', is_active=True, created_by_id=recipient.id,
        )
        db.add(escalation)
        db.flush()

        def make_case(key):
            return ReconciliationInvestigation(
                external_key=key, candidate_type="UNMATCHED_BANK_DEBIT",
                source_type="BANK_STATEMENT_LINE", source_id=9001,
                title="Test reconciliation escalation",
                summary="Test-only case for durable escalation intent generation.",
                severity="HIGH", status="OPEN", opened_by_id=recipient.id,
                opened_at=now - timedelta(hours=2), updated_at=now - timedelta(hours=2),
                sla_policy_id=sla_policy.id, sla_policy_version=91,
                sla_target_minutes=60, sla_warning_percent=80,
                sla_started_at=now - timedelta(hours=2),
                sla_due_at=now - timedelta(minutes=30), version=1,
            )

        first_case = make_case("test-escalation-case-001")
        db.add(first_case)
        db.commit()
        first_case_id = first_case.id

        first = evaluate_reconciliation_escalations(db, now=now)
        assert first["created"] == 1
        assert first["duplicates"] == 0
        db.commit()

        repeated = evaluate_reconciliation_escalations(db, now=now + timedelta(minutes=1))
        assert repeated["created"] == 0
        assert repeated["duplicates"] == 1
        db.commit()

        intent = db.query(ReconciliationNotificationOutbox).filter_by(
            investigation_id=first_case_id
        ).one()
        assert intent.recipient_user_id == recipient.id
        assert intent.event_type == "SLA_BREACHED"
        assert intent.channel == "IN_APP"
        assert intent.status == "PENDING"
        assert json.loads(intent.payload) == {
            "event_type": "SLA_BREACHED",
            "investigation_id": first_case_id,
            "severity": "HIGH",
        }

        db.add(ReconciliationNotificationPreference(
            user_id=recipient.id, event_type="SLA_BREACHED", channel="IN_APP",
            enabled=False, updated_at=now, updated_by_id=recipient.id,
        ))
        second_case = make_case("test-escalation-case-002")
        db.add(second_case)
        db.commit()
        second_case_id = second_case.id

        opted_out = evaluate_reconciliation_escalations(db, now=now + timedelta(minutes=2))
        assert opted_out["created"] == 0
        assert opted_out["opted_out"] == 2
        db.commit()

        assert db.query(ReconciliationNotificationOutbox).filter_by(
            investigation_id=second_case_id
        ).count() == 0
        assert db.query(ReconciliationNotificationOutbox).count() == 1
