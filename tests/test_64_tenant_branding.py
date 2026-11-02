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


def test_existing_tenant_admin_role_receives_branding_permission(multi_tenant_env):
    from backend.core.seed import seed_universal_hospital_data
    from backend.domains.identity.models import Permission, Role
    from sqlalchemy.orm import Session

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        # Simulate a tenant seeded before config:write was introduced.
        admin_role = db.query(Role).filter_by(code="ROLE_ADMIN").one()
        admin_role.permissions = [
            permission for permission in admin_role.permissions
            if permission.code != "config:write"
        ]
        db.commit()

        seed_universal_hospital_data(
            db=db,
            hospital_name="Avinya Default Hospital",
            branch_code="HQ-HYD-01",
            admin_email="admin@default.com",
            admin_password="AdminPassword123!",
        )
        admin_role = db.query(Role).filter_by(code="ROLE_ADMIN").one()
        permission_codes = {permission.code for permission in admin_role.permissions}
        assert "config:write" in permission_codes
        assert db.query(Permission).filter_by(code="config:write").one()


def test_brand_asset_upload_is_tenant_scoped_and_audited(
    client, multi_tenant_env, superuser_headers, apollo_admin_headers, monkeypatch, tmp_path
):
    import json
    from backend.control_plane.models import ControlPlaneAuditLog, TenantRegistry

    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("backend.domains.ui.router.scan_file_with_clamav", lambda path: None)
    image_bytes = b"\\x89PNG\\r\\n\\x1a\\n" + b"test-image-data"

    upload = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("tenant-logo.png", image_bytes, "image/png")},
    )
    assert upload.status_code == 200, upload.text
    asset_url = upload.json()["asset_url"]
    assert asset_url.startswith("/api/ui/tenant-branding/assets/")

    same_tenant = client.get(asset_url, headers=superuser_headers)
    assert same_tenant.status_code == 200
    assert same_tenant.headers["content-type"] == "image/png"
    assert same_tenant.content == image_bytes

    other_tenant = client.get(asset_url, headers=apollo_admin_headers)
    assert other_tenant.status_code == 404

    with multi_tenant_env["control_session_factory"]() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        branding = json.loads(tenant.ui_branding_json)
        assert branding["logo_url"] == asset_url
        audit = db.query(ControlPlaneAuditLog).filter_by(
            action="TENANT_BRAND_ASSET_UPLOADED",
            target_slug="default",
        ).one()
        assert "logo image" in audit.details


def test_brand_asset_upload_rejects_mismatched_file_signature(
    client, superuser_headers, monkeypatch, tmp_path
):
    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    response = client.post(
        "/api/ui/tenant-branding/assets?kind=favicon",
        headers=superuser_headers,
        files={"file": ("fake.png", b"not-a-png", "image/png")},
    )
    assert response.status_code == 415


def test_brand_asset_upload_rejects_svg_active_content(client, superuser_headers):
    response = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("logo.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert response.status_code == 415
