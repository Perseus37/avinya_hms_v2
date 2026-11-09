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



def test_reconciliation_finance_dashboard_returns_bounded_governance_aggregates(multi_tenant_env):
    from backend.domains.identity.models import User
    from backend.domains.procurement.investigations import get_reconciliation_finance_dashboard
    from backend.domains.procurement.models import ReconciliationInvestigation
    from fastapi import HTTPException

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        rows = [
            ReconciliationInvestigation(
                external_key="dashboard-case-open", candidate_type="UNMATCHED_BANK_DEBIT",
                source_type="BANK_STATEMENT_LINE", source_id=99101,
                title="Dashboard overdue case", summary="Synthetic test case for dashboard aggregation.",
                severity="CRITICAL", status="OPEN", opened_by_id=actor.id,
                opened_at=now - timedelta(days=9), updated_at=now,
                sla_started_at=now - timedelta(days=2), sla_due_at=now - timedelta(hours=2),
                version=1,
            ),
            ReconciliationInvestigation(
                external_key="dashboard-case-resolved", candidate_type="DUPLICATE_PAYMENT_REFERENCE",
                source_type="SUPPLIER_PAYMENT", source_id=99102,
                title="Dashboard resolved case", summary="Synthetic test case for closure quality aggregation.",
                severity="HIGH", status="RESOLVED", opened_by_id=actor.id,
                opened_at=now - timedelta(days=2), updated_at=now,
                resolved_at=now - timedelta(days=1), closed_by_id=actor.id,
                resolution="Reviewed and corrected.", root_cause="DUPLICATE_REFERENCE",
                resolution_quality_status="REJECTED", reopen_count=1, version=2,
            ),
        ]
        db.add_all(rows)
        db.commit()

        dashboard = get_reconciliation_finance_dashboard(db=db, window_days=30, queue_limit=10)
        assert dashboard["overview"]["total_investigations"] >= 2
        assert dashboard["overview"]["active_investigations"] >= 1
        assert dashboard["overview"]["overdue"] >= 1
        assert dashboard["active_by_severity"]["CRITICAL"] >= 1
        assert dashboard["closure_quality"]["rejected"] >= 1
        assert dashboard["reopening"]["cases_reopened"] >= 1
        assert dashboard["period_activity"]["root_causes"]
        assert dashboard["priority_queue"][0]["id"] == rows[0].id
        assert "summary" not in dashboard["priority_queue"][0]
        assert "source_reference" not in dashboard["priority_queue"][0]

        try:
            get_reconciliation_finance_dashboard(db=db, window_days=0, queue_limit=10)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Invalid dashboard window must be rejected")

        try:
            get_reconciliation_finance_dashboard(db=db, window_days=30, queue_limit=1000)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Unbounded dashboard queue must be rejected")


def test_reconciliation_recurrence_summary_groups_repeated_patterns_and_root_causes(multi_tenant_env):
    from backend.domains.identity.models import User
    from backend.domains.procurement.investigations import get_reconciliation_recurrence_summary
    from backend.domains.procurement.models import ReconciliationInvestigation
    from fastapi import HTTPException

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        rows = [
            ReconciliationInvestigation(
                external_key=f"recurrence-unmatched-{n}", candidate_type="UNMATCHED_BANK_DEBIT",
                source_type="BANK_STATEMENT_LINE", source_id=99200+n,
                title=f"Recurring debit {n}", summary="Synthetic recurrence test case.",
                severity="CRITICAL" if n == 1 else "HIGH", status="RESOLVED",
                opened_by_id=actor.id, opened_at=now-timedelta(days=n),
                updated_at=now, resolved_at=now-timedelta(days=n),
                closed_by_id=actor.id, resolution="Reconciled after review.",
                root_cause="DUPLICATE_REFERENCE",
                resolution_quality_status="REJECTED" if n == 1 else "APPROVED",
                reopen_count=1 if n == 1 else 0, version=2,
            )
            for n in (1, 2)
        ]
        rows.append(ReconciliationInvestigation(
            external_key="recurrence-unclassified-credit", candidate_type="UNCLASSIFIED_BANK_CREDIT",
            source_type="BANK_STATEMENT_LINE", source_id=99203,
            title="Unclassified credit", summary="A distinct pattern for the recurrence test.",
            severity="MEDIUM", status="OPEN", opened_by_id=actor.id,
            opened_at=now-timedelta(days=3), updated_at=now, version=1,
        ))
        db.add_all(rows)
        db.commit()

        result = get_reconciliation_recurrence_summary(db=db, window_days=30, min_occurrences=2, limit=10)
        pattern = next(x for x in result["repeated_exception_patterns"] if x["candidate_type"] == "UNMATCHED_BANK_DEBIT")
        cause = next(x for x in result["recurring_recorded_root_causes"] if x["root_cause"] == "DUPLICATE_REFERENCE")
        assert pattern["investigations"] == 2
        assert pattern["distinct_sources"] == 2
        assert pattern["critical_cases"] == 1
        assert pattern["reopens"] == 1
        assert cause["resolved_cases"] == 2
        assert cause["rejected_quality_reviews"] == 1
        assert "summary" not in pattern
        assert "source_id" not in pattern

        for kwargs in (
            {"window_days": 0, "min_occurrences": 2, "limit": 10},
            {"window_days": 30, "min_occurrences": 1, "limit": 10},
            {"window_days": 30, "min_occurrences": 2, "limit": 1000},
        ):
            try:
                get_reconciliation_recurrence_summary(db=db, **kwargs)
            except HTTPException as exc:
                assert exc.status_code == 422
            else:
                raise AssertionError("Invalid recurrence query bounds must be rejected")


def test_monthly_reconciliation_governance_report_is_immutable_and_tenant_scoped(multi_tenant_env):
    import hashlib
    from datetime import datetime, timezone
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError
    from backend.domains.identity.models import User
    from backend.domains.procurement.investigations import (
        GovernanceReportGenerate,
        generate_reconciliation_governance_report,
        get_reconciliation_governance_report,
        list_reconciliation_governance_reports,
    )
    from backend.domains.procurement.models import (
        ReconciliationGovernanceReport,
        ReconciliationInvestigation,
        ReconciliationInvestigationEvent,
    )
    from fastapi import HTTPException

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    now = datetime.now(timezone.utc)
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_start = (current_month - timedelta(days=1)).replace(day=1)
    report_month = period_start.strftime("%Y-%m")
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        rows = [
            ReconciliationInvestigation(
                external_key=f"monthly-report-resolved-{n}", candidate_type="UNMATCHED_BANK_DEBIT",
                source_type="BANK_STATEMENT_LINE", source_id=99400+n,
                title=f"Monthly report resolved {n}", summary="Synthetic monthly report test data.",
                severity="HIGH", status="RESOLVED", opened_by_id=actor.id,
                opened_at=period_start + timedelta(days=2+n),
                updated_at=period_start + timedelta(days=5+n),
                resolved_at=period_start + timedelta(days=5+n), closed_by_id=actor.id,
                resolution="Private narrative must not be included in the report.",
                root_cause="DUPLICATE_REFERENCE",
                resolution_quality_status="REJECTED" if n == 1 else "APPROVED",
                reopen_count=1 if n == 1 else 0, sla_due_at=period_start + timedelta(days=4+n),
                version=2,
            ) for n in (1, 2)
        ]
        rows.append(ReconciliationInvestigation(
            external_key="monthly-report-open", candidate_type="UNMATCHED_BANK_DEBIT",
            source_type="BANK_STATEMENT_LINE", source_id=99403,
            title="Open report case", summary="Synthetic open report case.",
            severity="CRITICAL", status="OPEN", opened_by_id=actor.id,
            opened_at=period_start + timedelta(days=10), updated_at=now,
            sla_due_at=period_start + timedelta(days=12), version=1,
        ))
        db.add_all(rows)
        db.flush()
        db.add(ReconciliationInvestigationEvent(
            investigation_id=rows[0].id, event_type="REOPENED",
            from_status="RESOLVED", to_status="IN_REVIEW",
            actor_user_id=actor.id, details='{"reason":"test"}',
            occurred_at=period_start + timedelta(days=6),
        ))
        db.commit()

        created = generate_reconciliation_governance_report(
            payload=GovernanceReportGenerate(report_month=report_month), db=db, current_user=actor
        )
        assert created["report_month"] == report_month
        assert created["payload"]["activity"]["opened"] == 3
        assert created["payload"]["activity"]["resolved"] == 2
        assert created["payload"]["activity"]["reopened_events"] == 1
        assert created["payload"]["closure_quality"]["rejected"] == 1
        assert created["payload"]["closure_quality"]["approved"] == 1
        assert created["payload"]["sla"]["resolved_with_sla"] == 2
        assert created["payload"]["recurring_exception_patterns"][0]["investigations"] == 3
        assert created["payload"]["recurring_recorded_root_causes"][0]["resolved_cases"] == 2
        assert created["payload"]["backlog_at_generation"]["active"] >= 1
        canonical = json.dumps(created["payload"], ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        assert created["payload_sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        rendered = json.dumps(created["payload"])
        assert "Private narrative" not in rendered
        assert "source_id" not in rendered
        assert "99400" not in rendered
        assert "opened_by_id" not in rendered

        listing = list_reconciliation_governance_reports(db=db, current_user=actor, limit=10)
        assert listing["items"][0]["id"] == created["id"]
        detail = get_reconciliation_governance_report(report_id=created["id"], db=db, current_user=actor)
        assert detail["payload_sha256"] == created["payload_sha256"]
        assert detail["payload"] == created["payload"]

        try:
            generate_reconciliation_governance_report(
                payload=GovernanceReportGenerate(report_month=report_month), db=db, current_user=actor
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Duplicate monthly report generation must be rejected")

        try:
            generate_reconciliation_governance_report(
                payload=GovernanceReportGenerate(report_month=current_month.strftime("%Y-%m")),
                db=db, current_user=actor,
            )
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Current month must not be finalized")

        try:
            db.execute(update(ReconciliationGovernanceReport).where(
                ReconciliationGovernanceReport.id == created["id"]
            ).values(payload="tampered"))
            db.commit()
            raise AssertionError("Governance report UPDATE must be blocked by the database")
        except DBAPIError:
            db.rollback()




def test_investigation_root_cause_accepts_only_approved_categories():
    from backend.domains.procurement.investigations import InvestigationTransition
    from pydantic import ValidationError

    normalized = InvestigationTransition.model_validate({
        "to_status": "RESOLVED",
        "expected_version": 1,
        "root_cause": " duplicate reference ",
    })
    assert normalized.root_cause == "DUPLICATE_REFERENCE"

    try:
        InvestigationTransition.model_validate({
            "to_status": "RESOLVED",
            "expected_version": 1,
            "root_cause": "Patient Jane Doe, account 123456",
        })
    except ValidationError:
        pass
    else:
        raise AssertionError("Free-text root causes must be rejected")
