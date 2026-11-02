"""Regression tests for tenant-scoped white-label branding."""

import json

from backend.control_plane.models import ControlPlaneAuditLog, TenantRegistry


BRANDING_URL = "/api/ui/tenant-branding"


def test_tenant_branding_bootstrap_is_public_and_tenant_scoped(client, multi_tenant_env):
    control_factory = multi_tenant_env["control_session_factory"]
    with control_factory() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="apollo").one()
        tenant.ui_branding_json = json.dumps({
            "display_name": "Apollo Care",
            "primary_color": "#123456",
            "private_internal_setting": "must-not-leak",
        })
        db.commit()

    response = client.get(BRANDING_URL, headers={"X-Hospital-Subdomain": "apollo"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_slug"] == "apollo"
    assert body["display_name"] == "Apollo Care"
    assert body["primary_color"] == "#123456"
    assert "private_internal_setting" not in body


def test_tenant_admin_can_update_branding_and_audit_is_written(client, multi_tenant_env, superuser_headers):
    payload = {
        "display_name": "Default Medical Centre",
        "tagline": "Care with confidence",
        "logo_url": "/assets/tenant-logo.svg",
        "favicon_url": "https://cdn.example.test/tenant-icon.png",
        "primary_color": "#112233",
        "secondary_color": "#223344",
        "accent_color": "#334455",
    }
    response = client.put(BRANDING_URL, headers=superuser_headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == payload["display_name"]
    assert response.json()["primary_color"] == payload["primary_color"]

    control_factory = multi_tenant_env["control_session_factory"]
    with control_factory() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        saved = json.loads(tenant.ui_branding_json)
        assert saved["display_name"] == payload["display_name"]
        assert saved["logo_url"] == payload["logo_url"]
        audit = db.query(ControlPlaneAuditLog).filter_by(
            action="TENANT_BRANDING_UPDATED",
            target_slug="default",
        ).one()
        assert audit.actor == "admin@default.com"


def test_branding_update_preserves_unrecognized_tenant_settings(client, multi_tenant_env, superuser_headers):
    control_factory = multi_tenant_env["control_session_factory"]
    with control_factory() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        tenant.ui_branding_json = json.dumps({
            "display_name": "Before",
            "custom_invoice_footer": "Keep this",
            "future_feature_flag": {"enabled": True},
        })
        db.commit()

    response = client.put(
        BRANDING_URL,
        headers=superuser_headers,
        json={"display_name": "After"},
    )
    assert response.status_code == 200, response.text

    with control_factory() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        saved = json.loads(tenant.ui_branding_json)
        assert saved["custom_invoice_footer"] == "Keep this"
        assert saved["future_feature_flag"] == {"enabled": True}
        assert saved["display_name"] == "After"


def test_non_admin_cannot_update_tenant_branding(client, doctor_headers):
    response = client.put(
        BRANDING_URL,
        headers=doctor_headers,
        json={"display_name": "Unauthorized Branding"},
    )
    assert response.status_code == 403


def test_branding_update_rejects_invalid_color_and_unsafe_asset_url(client, superuser_headers):
    invalid_color = client.put(
        BRANDING_URL,
        headers=superuser_headers,
        json={"display_name": "Valid Name", "primary_color": "red"},
    )
    assert invalid_color.status_code == 422

    unsafe_url = client.put(
        BRANDING_URL,
        headers=superuser_headers,
        json={"display_name": "Valid Name", "logo_url": "javascript:alert(1)"},
    )
    assert unsafe_url.status_code == 422


def test_branding_update_rejects_token_from_another_tenant(client, apollo_admin_headers):
    spoofed_headers = {
        "Authorization": apollo_admin_headers["Authorization"],
        "X-Hospital-Subdomain": "default",
    }
    response = client.put(
        BRANDING_URL,
        headers=spoofed_headers,
        json={"display_name": "Cross Tenant Attempt"},
    )
    assert response.status_code == 401
