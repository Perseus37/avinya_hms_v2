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
