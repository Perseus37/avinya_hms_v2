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
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"test-image-data"

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


def test_brand_asset_upload_fails_closed_when_malware_scanner_is_unavailable(
    client, superuser_headers, monkeypatch, tmp_path
):
    from fastapi import HTTPException

    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))

    def scanner_unavailable(_path):
        raise HTTPException(status_code=503, detail="Scanner unavailable.")

    monkeypatch.setattr("backend.domains.ui.router.scan_file_with_clamav", scanner_unavailable)
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"test-image-data"
    response = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("tenant-logo.png", image_bytes, "image/png")},
    )
    assert response.status_code == 503
    asset_directory = tmp_path / "default" / "branding-assets"
    assert not asset_directory.exists() or list(asset_directory.iterdir()) == []


def test_replacing_brand_asset_removes_only_the_unreferenced_previous_file(
    client, multi_tenant_env, superuser_headers, monkeypatch, tmp_path
):
    from pathlib import Path

    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("backend.domains.ui.router.scan_file_with_clamav", lambda path: None)
    headers = superuser_headers
    first = b"\x89PNG\r\n\x1a\nfirst-image"
    second = b"\x89PNG\r\n\x1a\nsecond-image"

    first_response = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=headers,
        files={"file": ("first.png", first, "image/png")},
    )
    assert first_response.status_code == 200, first_response.text
    first_url = first_response.json()["asset_url"]
    first_path = Path(tmp_path / "default" / "branding-assets" / first_url.rsplit("/", 1)[-1])
    assert first_path.is_file()

    second_response = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=headers,
        files={"file": ("second.png", second, "image/png")},
    )
    assert second_response.status_code == 200, second_response.text
    second_url = second_response.json()["asset_url"]
    second_path = Path(tmp_path / "default" / "branding-assets" / second_url.rsplit("/", 1)[-1])

    assert second_path.is_file()
    assert not first_path.exists()
    with multi_tenant_env["control_session_factory"]() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        assert json.loads(tenant.ui_branding_json)["logo_url"] == second_url


def test_replacing_logo_retains_previous_asset_when_favicon_still_uses_it(
    client, multi_tenant_env, superuser_headers, monkeypatch, tmp_path
):
    from pathlib import Path

    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("backend.domains.ui.router.scan_file_with_clamav", lambda path: None)
    first = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("shared.png", b"\x89PNG\r\n\x1a\nshared-image", "image/png")},
    )
    assert first.status_code == 200, first.text
    shared_url = first.json()["asset_url"]

    with multi_tenant_env["control_session_factory"]() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        branding = json.loads(tenant.ui_branding_json)
        branding["favicon_url"] = shared_url
        tenant.ui_branding_json = json.dumps(branding)
        db.commit()

    replacement = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("replacement.png", b"\x89PNG\r\n\x1a\nreplacement-image", "image/png")},
    )
    assert replacement.status_code == 200, replacement.text

    shared_path = Path(tmp_path / "default" / "branding-assets" / shared_url.rsplit("/", 1)[-1])
    assert shared_path.is_file()
    with multi_tenant_env["control_session_factory"]() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        branding = json.loads(tenant.ui_branding_json)
        assert branding["favicon_url"] == shared_url
        assert branding["logo_url"] == replacement.json()["asset_url"]


def test_failed_brand_asset_database_commit_keeps_previous_asset_and_removes_new_file(
    client, multi_tenant_env, superuser_headers, monkeypatch, tmp_path
):
    import pytest
    from sqlalchemy.orm import Session

    monkeypatch.setattr("backend.domains.ui.router.settings.ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("backend.domains.ui.router.scan_file_with_clamav", lambda path: None)

    first = client.post(
        "/api/ui/tenant-branding/assets?kind=logo",
        headers=superuser_headers,
        files={"file": ("existing.png", b"\x89PNG\r\n\x1a\nexisting-image", "image/png")},
    )
    assert first.status_code == 200, first.text
    previous_url = first.json()["asset_url"]
    asset_directory = tmp_path / "default" / "branding-assets"
    previous_path = asset_directory / previous_url.rsplit("/", 1)[-1]
    assert previous_path.is_file()

    original_commit = Session.commit

    def fail_brand_upload_commit(session):
        if any(
            getattr(item, "action", None) == "TENANT_BRAND_ASSET_UPLOADED"
            for item in session.new
        ):
            raise RuntimeError("simulated branding commit failure")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_brand_upload_commit)
    with pytest.raises(RuntimeError, match="simulated branding commit failure"):
        client.post(
            "/api/ui/tenant-branding/assets?kind=logo",
            headers=superuser_headers,
            files={"file": ("replacement.png", b"\x89PNG\r\n\x1a\nreplacement-image", "image/png")},
        )

    assert previous_path.is_file()
    assert list(asset_directory.iterdir()) == [previous_path]
    with multi_tenant_env["control_session_factory"]() as db:
        tenant = db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
        assert json.loads(tenant.ui_branding_json)["logo_url"] == previous_url

def test_untrusted_forwarded_host_cannot_change_tenant_routing(monkeypatch):
    from starlette.requests import Request

    from backend.core.config import settings
    from backend.core.database import extract_subdomain_slug

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_HEADER_TENANT_OVERRIDE", False, raising=False)
    monkeypatch.setattr(settings, "BASE_DOMAIN", "example.test")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "198.51.100.10/32")

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/ui/tenant-branding/assets/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
            "headers": [
                (b"host", b"default.example.test"),
                (b"x-forwarded-host", b"apollo.example.test"),
                (b"x-hospital-subdomain", b"apollo"),
            ],
            "client": ("203.0.113.25", 43120),
            "server": ("default.example.test", 443),
            "scheme": "https",
            "query_string": b"",
        }
    )

    assert extract_subdomain_slug(request) == "default"


def test_configured_trusted_proxy_can_supply_forwarded_tenant_host(monkeypatch):
    from starlette.requests import Request

    from backend.core.config import settings
    from backend.core.database import extract_subdomain_slug

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_HEADER_TENANT_OVERRIDE", False)
    monkeypatch.setattr(settings, "BASE_DOMAIN", "example.test")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "198.51.100.0/24")

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/ui/tenant-branding",
            "headers": [
                (b"host", b"internal-api"),
                (b"x-forwarded-host", b"apollo.example.test"),
            ],
            "client": ("198.51.100.10", 43120),
            "server": ("internal-api", 8000),
            "scheme": "https",
            "query_string": b"",
        }
    )

    assert extract_subdomain_slug(request) == "apollo"

