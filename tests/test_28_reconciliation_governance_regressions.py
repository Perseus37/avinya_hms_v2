from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker


def test_reopen_rate_counts_distinct_cases_and_reports_reopen_events(
    client, superuser_headers, multi_tenant_env
):
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationExceptionEvent,
    )

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        case = ProcurementReconciliationException(
            fingerprint="GOVERNANCE:REOPEN-RATE:DISTINCT-CASE",
            exception_type="UNMATCHED_BANK_DEBIT",
            severity="HIGH",
            status="OPEN",
            reference_type="BANK_STATEMENT_LINE",
            reference_id=990102,
            amount_paise=1000,
            matched_amount_paise=0,
            unmatched_amount_paise=1000,
            summary="Distinct reopen-rate regression case.",
            detection_snapshot={},
            first_detected_at=now - timedelta(days=3),
            last_detected_at=now,
            root_cause_code="BANK_FEED_DELAY",
            reopen_count=2,
        )
        db.add(case)
        db.flush()
        db.add_all([
            ProcurementReconciliationExceptionEvent(
                exception_id=case.id,
                event_type="STATUS_CHANGED",
                old_status="IN_REVIEW",
                new_status="RESOLVED",
                event_metadata={},
                occurred_at=now - timedelta(days=2),
            ),
            ProcurementReconciliationExceptionEvent(
                exception_id=case.id,
                event_type="REOPENED",
                old_status="RESOLVED",
                new_status="OPEN",
                event_metadata={"prior_resolution": {"root_cause_code": "BANK_FEED_DELAY"}},
                occurred_at=now - timedelta(days=1, hours=12),
            ),
            ProcurementReconciliationExceptionEvent(
                exception_id=case.id,
                event_type="STATUS_CHANGED",
                old_status="IN_REVIEW",
                new_status="RESOLVED",
                event_metadata={},
                occurred_at=now - timedelta(days=1),
            ),
            ProcurementReconciliationExceptionEvent(
                exception_id=case.id,
                event_type="REOPENED",
                old_status="RESOLVED",
                new_status="OPEN",
                event_metadata={"prior_resolution": {"root_cause_code": "BANK_FEED_DELAY"}},
                occurred_at=now - timedelta(hours=12),
            ),
        ])
        db.commit()

    response = client.get(
        "/v1/api/procurement/reconciliation/governance/closure-quality",
        headers=superuser_headers,
        params={"from_date": (now - timedelta(days=3)).date().isoformat()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolved_count"] == 1
    assert body["reopened_cases"] == 1
    assert body["reopen_events"] == 2
    assert body["reopen_rate_percent"] == 100.0
    root = next(item for item in body["root_causes"] if item["root_cause_code"] == "BANK_FEED_DELAY")
    assert root["reopened_count"] == 1
    assert root["reopen_events"] == 2
