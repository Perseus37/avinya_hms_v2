"""Tests for Security Audit Log Export and SIEM Streaming Integration (M-14)."""

import json
from datetime import datetime, timezone
import pytest


def test_query_security_events_default(client, superuser_headers):
    """Verifies that security events across ledgers can be retrieved with pagination."""
    res = client.get(
        "/v1/api/audit/security-events",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "total_events" in data
    assert "events" in data
    assert isinstance(data["events"], list)


def test_query_security_events_filtered(client, superuser_headers):
    """Verifies filtering by category and severity."""
    res = client.get(
        "/v1/api/audit/security-events?category=PRIVACY_CONSENT&limit=10",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    data = res.json()
    for ev in data["events"]:
        assert ev["category"] == "PRIVACY_CONSENT"


def test_stream_security_events_ndjson(client, superuser_headers):
    """Verifies that the /stream endpoint returns valid newline-delimited JSON (NDJSON)."""
    res = client.get(
        "/v1/api/audit/stream?limit=100",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    assert "application/x-ndjson" in res.headers["content-type"]

    lines = [line.strip() for line in res.text.split("\n") if line.strip()]
    for line in lines:
        parsed = json.loads(line)
        assert "event_id" in parsed
        assert "timestamp" in parsed
        assert "category" in parsed
        assert "severity" in parsed
        assert "action" in parsed


def test_siem_webhook_ssrf_protection_blocks_loopback(client, superuser_headers):
    """Verifies that loopback and internal addresses are blocked with 400 Bad Request."""
    res = client.post(
        "/v1/api/audit/siem/webhook-test",
        headers=superuser_headers,
        json={"webhook_url": "http://127.0.0.1:19999/siem/invalid"},
    )
    assert res.status_code == 400
    assert "SSRF Protection" in res.json()["message"]


def test_siem_webhook_ssrf_protection_blocks_cgnat(client, superuser_headers, monkeypatch):
    """N-34: Verifies CGNAT (100.64.0.0/10) IP addresses are blocked by SSRF guard."""
    import socket
    orig_getaddrinfo = socket.getaddrinfo

    def mock_getaddrinfo(host, port, *args, **kwargs):
        if host == "internal-cgnat-service.local":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.1", 80))]
        return orig_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    res = client.post(
        "/v1/api/audit/siem/webhook-test",
        headers=superuser_headers,
        json={"webhook_url": "http://internal-cgnat-service.local/webhook"},
    )
    assert res.status_code == 400
    assert "SSRF Protection" in res.json()["message"]


def test_security_events_with_breach_incident(client, superuser_headers):
    """Verifies SIEM export queries successfully when a PrivacyDataBreachIncident exists."""
    from backend.core.database import tenant_engine_pool
    from sqlalchemy.orm import Session
    from backend.domains.privacy.models import PrivacyDataBreachIncident

    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(bind=engine) as session:
        breach = PrivacyDataBreachIncident(
            incident_code="BR-TEST-001",
            title="Test Phishing Incident",
            description="Suspicious email attachment flagged by EDR",
            severity="HIGH",
            status="REPORTED",
            breach_type="CONFIDENTIALITY",
            affected_data_categories=["PATIENT_DEMOGRAPHICS"],
            estimated_affected_subjects=5,
            reported_by_user_id=1,
        )
        session.add(breach)
        session.commit()

    res = client.get(
        "/v1/api/audit/security-events?category=DATA_BREACH",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) >= 1
    assert any(ev["details"]["incident_code"] == "BR-TEST-001" for ev in events)


def test_unauthorized_user_blocked_from_security_events(client, nurse_headers):
    """Users without privacy:read or audit permission are blocked with 403 Forbidden."""
    res = client.get(
        "/v1/api/audit/security-events",
        headers=nurse_headers,
    )
    assert res.status_code == 403



def test_stream_export_register_persists_exact_digest_and_metadata(client, superuser_headers):
    import hashlib
    from backend.core.database import tenant_engine_pool
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from backend.domains.audit.models import SecurityAuditExportRegister

    response = client.get("/v1/api/audit/stream?category=DATA_BREACH&limit=25", headers=superuser_headers)
    assert response.status_code == 200
    assert response.content.endswith(b"\n") or response.content == b""
    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(bind=engine) as session:
        row = session.execute(
            select(SecurityAuditExportRegister).order_by(SecurityAuditExportRegister.id.desc())
        ).scalars().first()
        assert row is not None
        assert row.payload_sha256 == hashlib.sha256(response.content).hexdigest()
        assert row.byte_count == len(response.content)
        assert row.category == "DATA_BREACH"
        assert row.actor_user_id == 1

    listing = client.get("/v1/api/audit/exports?limit=10", headers=superuser_headers)
    assert listing.status_code == 200
    item = next(x for x in listing.json()["items"] if x["payload_sha256"] == hashlib.sha256(response.content).hexdigest())
    detail = client.get(f"/v1/api/audit/exports/{item['id']}", headers=superuser_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["criteria"]["category"] == "DATA_BREACH"
    assert data["payload_sha256"] == hashlib.sha256(response.content).hexdigest()
    assert "payload" not in data
    assert "events" not in data


def test_audit_export_register_read_requires_privacy_permission(client, nurse_headers):
    assert client.get("/v1/api/audit/exports", headers=nurse_headers).status_code == 403


def test_audit_export_register_is_append_only_on_sqlite_metadata():
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError
    from backend.core.database import Base
    from backend.domains.audit.models import SecurityAuditExportRegister

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[SecurityAuditExportRegister.__table__])
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO security_audit_export_register "
            "(id, exported_at, actor_user_id, schema_version, event_count, byte_count, criteria_json, payload_sha256) "
            "VALUES (987654, CURRENT_TIMESTAMP, 987654, 1, 0, 0, '{}', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')"
        ))
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("UPDATE security_audit_export_register SET event_count = 1 WHERE id = 987654"))
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM security_audit_export_register WHERE id = 987654"))
