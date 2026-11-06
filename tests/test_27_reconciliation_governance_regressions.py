from datetime import datetime, timedelta, timezone


def test_future_effective_policy_is_not_reported_as_active(client, superuser_headers):
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    created = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "response_targets_hours": {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 12, "LOW": 48},
            "escalation_levels": [{"after_hours": 1}],
            "change_reason": "Schedule a future effective policy without activating it early.",
        },
    )
    assert created.status_code == 201, created.text
    published = client.post(
        f"/v1/api/procurement/reconciliation/escalation-policies/{created.json()['id']}/publish",
        headers=superuser_headers,
        json={"effective_from": future},
    )
    assert published.status_code == 200, published.text
    listed = client.get(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["active_policy_id"] is None
