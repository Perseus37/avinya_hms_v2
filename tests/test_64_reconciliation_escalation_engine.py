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

        first = evaluate_reconciliation_escalations(db, now=now, batch_size=1)
        assert first["created"] == 1
        assert first["duplicates"] == 0
        assert first["next_after_case_id"] == first_case_id
        db.commit()

        repeated = evaluate_reconciliation_escalations(db, now=now + timedelta(minutes=1), batch_size=1)
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

        from fastapi import HTTPException
        from backend.domains.procurement.notification_inbox import (
            list_my_reconciliation_notifications,
            mark_my_reconciliation_notification_read,
        )

        inbox = list_my_reconciliation_notifications(db=db, actor=recipient)
        assert inbox["unread_count"] == 1
        assert len(inbox["items"]) == 1
        assert inbox["items"][0]["investigation_id"] == first_case_id
        assert inbox["items"][0]["severity"] == "HIGH"
        assert "payload" not in inbox["items"][0]
        assert "idempotency_key" not in inbox["items"][0]

        read_result = mark_my_reconciliation_notification_read(
            notification_id=intent.id, db=db, actor=recipient
        )
        assert read_result["is_read"] is True
        first_read_at = read_result["read_at"]
        repeated_read = mark_my_reconciliation_notification_read(
            notification_id=intent.id, db=db, actor=recipient
        )
        assert repeated_read["read_at"] == first_read_at
        assert list_my_reconciliation_notifications(db=db, actor=recipient)["unread_count"] == 0

        other_user = db.query(User).filter(User.id != recipient.id).first()
        if other_user is not None:
            assert list_my_reconciliation_notifications(
                db=db, actor=other_user
            )["items"] == []
            try:
                mark_my_reconciliation_notification_read(
                    notification_id=intent.id, db=db, actor=other_user
                )
                assert False, "A different user must not read another recipient's notification."
            except HTTPException as exc:
                assert exc.status_code == 404

        db.add(ReconciliationNotificationPreference(
            user_id=recipient.id, event_type="SLA_BREACHED", channel="IN_APP",
            enabled=False, updated_at=now, updated_by_id=recipient.id,
        ))
        second_case = make_case("test-escalation-case-002")
        db.add(second_case)
        db.commit()
        second_case_id = second_case.id

        opted_out = evaluate_reconciliation_escalations(
            db, now=now + timedelta(minutes=2), after_case_id=first_case_id
        )
        assert opted_out["created"] == 0
        assert opted_out["opted_out"] == 1
        db.commit()

        assert db.query(ReconciliationNotificationOutbox).filter_by(
            investigation_id=second_case_id
        ).count() == 0
        assert db.query(ReconciliationNotificationOutbox).count() == 1
