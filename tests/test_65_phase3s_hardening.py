from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session


def test_reconciliation_assignment_rejects_inactive_assignee(multi_tenant_env):
    from fastapi import HTTPException
    from backend.domains.identity.models import User, UserStatusEnum
    from backend.domains.procurement.investigations import InvestigationAssign, assign_reconciliation_investigation
    from backend.domains.procurement.models import ReconciliationInvestigation

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        inactive = User(login_id="inactive-recon-assignee", email="inactive-recon-assignee@example.test",
                        hashed_password="test-only", full_name="Inactive Assignee",
                        status=UserStatusEnum.SUSPENDED)
        case = ReconciliationInvestigation(
            external_key="hardening-inactive-assignee", candidate_type="UNMATCHED_BANK_DEBIT",
            source_type="BANK_STATEMENT_LINE", source_id=880001, title="Inactive assignee regression",
            summary="Regression case for rejecting inactive investigation assignees.", severity="HIGH",
            status="OPEN", opened_by_id=actor.id, opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc), version=1)
        db.add_all([inactive, case])
        db.commit()
        with pytest.raises(HTTPException) as exc:
            assign_reconciliation_investigation(
                investigation_id=case.id,
                payload=InvestigationAssign(assigned_to_id=inactive.id, expected_version=1),
                db=db, current_user=actor)
        assert exc.value.status_code == 409
        db.refresh(case)
        assert case.assigned_to_id is None and case.version == 1


def test_reconciliation_investigation_events_support_keyset_pagination(multi_tenant_env):
    from backend.domains.identity.models import User
    from backend.domains.procurement.investigations import list_reconciliation_investigation_events
    from backend.domains.procurement.models import ReconciliationInvestigation, ReconciliationInvestigationEvent

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        case = ReconciliationInvestigation(
            external_key="hardening-event-pagination", candidate_type="UNMATCHED_BANK_DEBIT",
            source_type="BANK_STATEMENT_LINE", source_id=880002, title="Event pagination regression",
            summary="Regression case for bounded investigation event history.", severity="MEDIUM",
            status="OPEN", opened_by_id=actor.id, opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc), version=1)
        db.add(case)
        db.flush()
        db.add_all([ReconciliationInvestigationEvent(
            investigation_id=case.id, event_type=f"TEST_EVENT_{n}", actor_user_id=actor.id,
            occurred_at=datetime.now(timezone.utc)) for n in range(5)])
        db.commit()
        first = list_reconciliation_investigation_events(
            investigation_id=case.id, before_id=None, limit=2, db=db, _=actor)
        second = list_reconciliation_investigation_events(
            investigation_id=case.id, before_id=first[-1]["id"], limit=2, db=db, _=actor)
        assert len(first) == len(second) == 2
        assert first[0]["id"] > first[1]["id"] > second[0]["id"] > second[1]["id"]


def test_reconciliation_candidate_discovery_returns_continuation_cursor(multi_tenant_env):
    from sqlalchemy import event
    from backend.domains.identity.models import User
    from backend.domains.procurement.bank_reconciliation import list_reconciliation_candidates
    from backend.domains.procurement.models import BankStatementBatch, BankStatementLine

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    statements = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        if "procurement_supplier_payment_bank_matches" in statement:
            statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        with Session(engine) as db:
            actor = db.query(User).filter(User.email == "admin@default.com").one()
            batch = BankStatementBatch(
                account_key="CURSOR-TEST", account_label="Test account",
                statement_reference="CURSOR-TEST-STATEMENT", period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31), opening_balance_paise=0,
                closing_balance_paise=100100, imported_by_id=actor.id)
            db.add(batch)
            db.flush()
            db.add_all([BankStatementLine(
                batch_id=batch.id, account_key="CURSOR-TEST",
                bank_transaction_id=f"CURSOR-TXN-{n:04d}", transaction_date=date(2026, 1, 15),
                direction="CREDIT", amount_paise=100, bank_reference=f"CURSOR-REF-{n:04d}")
                for n in range(1001)])
            db.commit()
            first = list_reconciliation_candidates(
                as_of=date(2026, 2, 1), limit=100, cursor=None, db=db, _=actor)
            second = list_reconciliation_candidates(
                as_of=date(2026, 2, 1), limit=100, cursor=first["next_cursor"], db=db, _=actor)
            assert len(first["items"]) == len(second["items"]) == 100
            assert first["truncated"] and first["next_cursor"]
            assert second["items"][0]["source_id"] != first["items"][0]["source_id"]

        aggregate_queries = [
            statement for statement in statements
            if "group by" in statement
        ]
        assert any("statement_line_id in" in statement for statement in aggregate_queries)
        assert any("supplier_payment_id in" in statement for statement in aggregate_queries)
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)


def test_governance_report_uses_resolution_event_history_after_reopen(multi_tenant_env):
    """Reopening a case must not erase resolution activity from its historical month."""
    import json
    from datetime import timedelta
    from backend.domains.identity.models import User
    from backend.domains.procurement.investigations import _governance_report_payload
    from backend.domains.procurement.models import (
        ReconciliationInvestigation, ReconciliationInvestigationEvent,
    )

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    period_start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 12, 1, tzinfo=timezone.utc)
    resolved_at = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        case = ReconciliationInvestigation(
            external_key="hardening-governance-reopened",
            candidate_type="UNMATCHED_BANK_DEBIT",
            source_type="BANK_STATEMENT_LINE",
            source_id=880003,
            title="Governance reopened case",
            summary="Regression case for historical resolution reporting.",
            severity="HIGH",
            status="IN_REVIEW",
            opened_by_id=actor.id,
            opened_at=period_start - timedelta(days=1),
            updated_at=period_end,
            sla_due_at=resolved_at - timedelta(hours=1),
            resolved_at=None,
            resolution=None,
            root_cause=None,
            resolution_quality_status="NOT_REVIEWED",
            version=4,
        )
        db.add(case)
        db.flush()
        second_case = ReconciliationInvestigation(
            external_key="hardening-governance-still-resolved",
            candidate_type="UNMATCHED_BANK_DEBIT",
            source_type="BANK_STATEMENT_LINE",
            source_id=880004,
            title="Governance still-resolved case",
            summary="Second case for root-cause recurrence aggregation.",
            severity="HIGH",
            status="RESOLVED",
            opened_by_id=actor.id,
            opened_at=period_start - timedelta(days=1),
            updated_at=period_end,
            sla_due_at=resolved_at - timedelta(hours=1),
            resolved_at=resolved_at + timedelta(days=1),
            resolution="Resolved with supporting evidence.",
            root_cause="TIMING_DIFFERENCE",
            resolution_quality_status="APPROVED",
            version=2,
        )
        db.add(second_case)
        db.flush()
        db.add_all([
            ReconciliationInvestigationEvent(
                investigation_id=case.id,
                event_type="STATUS_CHANGED",
                from_status="IN_REVIEW",
                to_status="RESOLVED",
                actor_user_id=actor.id,
                details=json.dumps({
                    "resolution": "Resolved with supporting evidence.",
                    "root_cause": "TIMING_DIFFERENCE",
                }),
                occurred_at=resolved_at,
            ),
            ReconciliationInvestigationEvent(
                investigation_id=case.id,
                event_type="REOPENED",
                from_status="RESOLVED",
                to_status="IN_REVIEW",
                actor_user_id=actor.id,
                details=json.dumps({
                    "previous_resolution": "Resolved with supporting evidence.",
                    "previous_root_cause": "TIMING_DIFFERENCE",
                }),
                occurred_at=resolved_at + timedelta(hours=1),
            ),
            ReconciliationInvestigationEvent(
                investigation_id=second_case.id,
                event_type="STATUS_CHANGED",
                from_status="IN_REVIEW",
                to_status="RESOLVED",
                actor_user_id=actor.id,
                details=json.dumps({
                    "resolution": "Resolved with supporting evidence.",
                    "root_cause": "TIMING_DIFFERENCE",
                }),
                occurred_at=resolved_at + timedelta(days=1),
            ),
        ])
        db.commit()

        snapshot = _governance_report_payload(
            db, period_start=period_start, period_end=period_end,
            generated_at=datetime(2026, 12, 2, tzinfo=timezone.utc),
        )

    assert snapshot["activity"]["resolved"] == 2
    assert snapshot["activity"]["reopened_events"] == 1
    assert snapshot["sla"]["resolved_with_sla"] == 2
    assert snapshot["sla"]["closed_late"] == 2
    assert snapshot["closure_quality"]["not_reviewed"] == 1
    assert snapshot["closure_quality"]["approved"] == 1
    assert snapshot["recurring_recorded_root_causes"] == [
        {"root_cause": "TIMING_DIFFERENCE", "resolved_cases": 2}
    ]


def test_reconciliation_duplicate_payment_reference_detected_across_source_windows(multi_tenant_env):
    """A normalized duplicate spanning two 1,000-payment windows is emitted once."""
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import (
        SupplierPayment, SupplierPaymentMethodEnum, VendorCategoryEnum, VendorMaster,
    )
    from backend.domains.procurement.bank_reconciliation import list_reconciliation_candidates

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        actor = db.query(User).filter(User.email == "admin@default.com").one()
        vendor = VendorMaster(
            code="CROSS-WINDOW-DUP",
            name="Cross-window duplicate test supplier",
            category=VendorCategoryEnum.GENERAL_SUPPLIES,
            contact_person="Test Contact",
            phone="9999999999",
            email="cross-window-duplicate@example.test",
            address="Test address",
            credit_period_days=30,
            is_active=True,
        )
        db.add(vendor)
        db.flush()

        payment_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
        payments = []
        for index in range(1001):
            reference = (
                "DUP REF 001" if index == 0
                else "DUPREF001" if index == 1000
                else f"CROSS-WINDOW-{index:04d}"
            )
            payments.append(SupplierPayment(
                vendor_id=vendor.id,
                payment_reference=reference,
                payment_method=SupplierPaymentMethodEnum.BANK_TRANSFER,
                payment_date=payment_date,
                amount_paise=10000,
                recorded_by_id=actor.id,
            ))
        db.add_all(payments)
        db.commit()

        first = list_reconciliation_candidates(
            as_of=date(2026, 2, 1), limit=2000, cursor=None, db=db, _=actor,
        )
        assert first["next_cursor"] is not None
        duplicate_candidates = [
            item for item in first["items"]
            if item["candidate_type"] == "POSSIBLE_DUPLICATE_PAYMENT_REFERENCE"
        ]
        assert len(duplicate_candidates) == 1
        duplicate = duplicate_candidates[0]
        assert duplicate["matching_payment_count"] == 2
        assert duplicate["source_ids"] == [payments[0].id]

        second = list_reconciliation_candidates(
            as_of=date(2026, 2, 1), limit=2000, cursor=first["next_cursor"], db=db, _=actor,
        )
        assert not any(
            item["candidate_type"] == "POSSIBLE_DUPLICATE_PAYMENT_REFERENCE"
            for item in second["items"]
        )


def test_investigation_create_rejects_unknown_or_mismatched_candidate_source_type():
    from pydantic import ValidationError
    from backend.domains.procurement.investigations import InvestigationCreate

    base = {
        "source_id": 1,
        "title": "Reconciliation exception",
        "summary": "A source requires a human reconciliation investigation.",
        "severity": "MEDIUM",
    }
    valid_pairs = [
        ("BANK_STATEMENT_LINE", "UNMATCHED_BANK_DEBIT"),
        ("BANK_STATEMENT_LINE", "PARTIALLY_MATCHED_BANK_DEBIT"),
        ("BANK_STATEMENT_LINE", "UNCLASSIFIED_BANK_CREDIT"),
        ("SUPPLIER_PAYMENT", "UNRECONCILED_SUPPLIER_PAYMENT"),
        ("SUPPLIER_PAYMENT", "PARTIALLY_RECONCILED_SUPPLIER_PAYMENT"),
        ("SUPPLIER_PAYMENT", "POSSIBLE_DUPLICATE_PAYMENT_REFERENCE"),
        ("SUPPLIER_PAYMENT_REQUEST", "OVERDUE_APPROVED_PAYMENT_REQUEST"),
    ]
    for source_type, candidate_type in valid_pairs:
        payload = InvestigationCreate.model_validate({
            **base, "source_type": source_type, "candidate_type": candidate_type,
        })
        assert payload.source_type == source_type
        assert payload.candidate_type == candidate_type

    invalid_pairs = [
        ("BANK_STATEMENT_LINE", "OVERDUE_APPROVED_PAYMENT_REQUEST"),
        ("SUPPLIER_PAYMENT", "UNMATCHED_BANK_DEBIT"),
        ("SUPPLIER_PAYMENT_REQUEST", "POSSIBLE_DUPLICATE_PAYMENT_REFERENCE"),
        ("SUPPLIER_PAYMENT", "ARBITRARY_FINANCE_EXCEPTION"),
    ]
    for source_type, candidate_type in invalid_pairs:
        with pytest.raises(ValidationError):
            InvestigationCreate.model_validate({
                **base, "source_type": source_type, "candidate_type": candidate_type,
            })
