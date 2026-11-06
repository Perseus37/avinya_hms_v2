from datetime import date, timedelta


def test_reconciliation_escalation_policy_is_versioned_and_effective(client, superuser_headers):
    invalid = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "response_targets_hours": {"CRITICAL": 0, "HIGH": 2, "MEDIUM": 8, "LOW": 24},
            "escalation_levels": [{"after_hours": 2}],
            "change_reason": "Invalid target should be rejected.",
        },
    )
    assert invalid.status_code == 422, invalid.text

    created = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "response_targets_hours": {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 12, "LOW": 48},
            "escalation_levels": [
                {"after_hours": 1, "notify_assignee": True, "notify_assigning_manager": True},
                {"after_hours": 4, "notify_assignee": True, "notify_assigning_manager": True, "notify_finance_managers": True},
            ],
            "notification_preferences": {
                "email_enabled": True, "assignee": True, "assigning_manager": True, "finance_managers": True,
            },
            "change_reason": "Align escalation deadlines with the approved finance risk appetite.",
        },
    )
    assert created.status_code == 201, created.text
    policy_id = created.json()["id"]
    published = client.post(
        f"/v1/api/procurement/reconciliation/escalation-policies/{policy_id}/publish",
        headers=superuser_headers,
        json={},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"

    listed = client.get(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["active_policy_id"] == policy_id
    active = next(item for item in listed.json()["items"] if item["id"] == policy_id)
    assert active["escalation_levels"][1]["notify_finance_managers"] is True


def test_reconciliation_governance_quality_and_dashboard_are_read_only(client, superuser_headers):
    quality = client.get(
        "/v1/api/procurement/reconciliation/governance/closure-quality",
        headers=superuser_headers,
    )
    assert quality.status_code == 200, quality.text
    assert "root_causes" in quality.json()
    assert "reopen_rate_percent" in quality.json()

    dashboard = client.get(
        "/v1/api/procurement/reconciliation/governance/dashboard",
        headers=superuser_headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    assert "overview" in dashboard.json()
    assert dashboard.json()["overview"]["total_cases"] >= 0


def test_reconciliation_monthly_governance_report_is_unique_per_period(client, superuser_headers):
    today = date.today()
    first_of_this_month = today.replace(day=1)
    period_end = first_of_this_month - timedelta(days=1)
    period_start = period_end.replace(day=1)
    payload = {"period_start": period_start.isoformat(), "period_end": period_end.isoformat()}

    created = client.post(
        "/v1/api/procurement/reconciliation/governance/monthly-reports",
        headers=superuser_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["snapshot"]["period_start"] == payload["period_start"]

    duplicate = client.post(
        "/v1/api/procurement/reconciliation/governance/monthly-reports",
        headers=superuser_headers,
        json=payload,
    )
    assert duplicate.status_code == 409, duplicate.text

    listed = client.get(
        "/v1/api/procurement/reconciliation/governance/monthly-reports",
        headers=superuser_headers,
    )
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == created.json()["id"] for item in listed.json()["items"])


def test_reconciliation_audit_export_register_lists_generated_packages(client, superuser_headers):
    response = client.get(
        "/v1/api/procurement/reconciliation/audit-exports",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    assert isinstance(response.json()["items"], list)


def test_assignment_event_snapshots_published_escalation_policy(
    client, superuser_headers, multi_tenant_env
):
    from datetime import datetime, timezone
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationExceptionEvent,
    )

    created = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "response_targets_hours": {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 12, "LOW": 48},
            "escalation_levels": [{"after_hours": 1}, {"after_hours": 4}],
            "change_reason": "Snapshot the active escalation policy on each assignment.",
        },
    )
    assert created.status_code == 201, created.text
    policy_id = created.json()["id"]
    published = client.post(
        f"/v1/api/procurement/reconciliation/escalation-policies/{policy_id}/publish",
        headers=superuser_headers,
        json={},
    )
    assert published.status_code == 200, published.text

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        assignee_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        assert assignee_id is not None
        now = datetime.now(timezone.utc)
        row = ProcurementReconciliationException(
            fingerprint="GOVERNANCE:POLICY-SNAPSHOT:990101",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=990101,
            amount_paise=1000, matched_amount_paise=0, unmatched_amount_paise=1000,
            summary="Escalation policy snapshot regression case.",
            detection_snapshot={}, first_detected_at=now, last_detected_at=now,
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    assigned = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/assignment",
        headers=superuser_headers,
        json={"assigned_to_id": assignee_id},
    )
    assert assigned.status_code == 200, assigned.text

    with session_factory() as db:
        event = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == exception_id,
            ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
        ).order_by(ProcurementReconciliationExceptionEvent.id.desc()).first()
        assert event is not None
        assert event.event_metadata["escalation_policy_id"] == policy_id
        assert event.event_metadata["escalation_policy_version"] == 1
        assert event.event_metadata["response_target_hours"] == 4
        assert len(event.event_metadata["escalation_levels"]) == 2
