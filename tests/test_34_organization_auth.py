from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.control_plane import app as control_app_module
from backend.control_plane.models import (
    Branch, BranchAccessSession, BranchMembership, BranchUserLink,
    ControlBase, HospitalGroup, OrganizationUser, TenantRegistry,
)
from backend.core.database import get_control_db
from backend.core.dependencies import get_redis
from backend.domains.identity.passwords import pwd_context
from backend.security.totp import totp_code


def test_group_owner_must_enroll_mfa_and_gets_revocable_central_session(monkeypatch):
    from backend.control_plane.api.routers import organization_auth
    from backend.control_plane.services import auth as operator_auth

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ControlBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as db:
        group = HospitalGroup(code="ACME-HEALTH", name="Acme Health", status="ACTIVE")
        db.add(group)
        db.flush()
        db.add(
            OrganizationUser(
                group_id=group.id,
                email="owner@acme.example",
                email_normalized="owner@acme.example",
                full_name="Acme Owner",
                group_role="OWNER",
                password_hash=pwd_context.hash("SecureOwnerPass123!"),
                status="ACTIVE",
                email_verified_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def override_get_control_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    class TestRedis:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex=None):
            self.values[key] = value
            return True

    monkeypatch.setattr(control_app_module, "ControlSessionLocal", SessionLocal)
    monkeypatch.setattr(organization_auth, "ControlSessionLocal", SessionLocal)
    monkeypatch.setattr(operator_auth, "ControlSessionLocal", SessionLocal)
    monkeypatch.setattr(
        organization_auth, "encrypt_tenant_secret", lambda value: f"test:{value}"
    )
    monkeypatch.setattr(
        organization_auth,
        "decrypt_tenant_secret",
        lambda value: value.removeprefix("test:"),
    )
    control_app_module.app.dependency_overrides[get_control_db] = override_get_control_db
    control_app_module.app.dependency_overrides[get_redis] = lambda: TestRedis()

    try:
        with TestClient(control_app_module.app) as client:
            login = client.post(
                "/api/organization-auth/login",
                json={
                    "email": "OWNER@acme.example",
                    "password": "SecureOwnerPass123!",
                    "group_code": "acme-health",
                },
            )
            assert login.status_code == 200, login.text
            challenge = login.json()
            assert challenge["mfa_setup_required"] is True
            assert "access_token" not in challenge

            setup = client.post(
                "/api/organization-auth/mfa/setup",
                json={"mfa_token": challenge["mfa_token"]},
            )
            assert setup.status_code == 200, setup.text
            secret = setup.json()["secret"]

            confirm = client.post(
                "/api/organization-auth/mfa/confirm",
                json={
                    "mfa_token": challenge["mfa_token"],
                    "code": totp_code(secret),
                },
            )
            assert confirm.status_code == 200, confirm.text
            access_token = confirm.json()["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

            with SessionLocal() as db:
                group = db.query(HospitalGroup).filter_by(code="ACME-HEALTH").one()
                registry = TenantRegistry(
                    hospital_name="Acme Main Hospital",
                    branch_code="ACME-MAIN",
                    subdomain_slug="acme-main",
                    db_name="acme_main_db",
                    admin_email="admin@acme.example",
                    jwt_secret_key="branch-test-signing-key",
                    backup_encryption_key="branch-test-backup-key",
                )
                db.add(registry)
                db.flush()
                branch = Branch(
                    group_id=group.id,
                    tenant_registry_id=registry.id,
                    code="ACME-MAIN",
                    name="Acme Main Hospital",
                    status="ACTIVE",
                )
                db.add(branch)
                db.flush()
                membership = BranchMembership(
                    organization_user_id=1,
                    branch_id=branch.id,
                    group_id=group.id,
                    status="ACTIVE",
                )
                db.add(membership)
                db.flush()
                db.add(BranchUserLink(
                    membership_id=membership.id,
                    organization_user_id=1,
                    branch_id=branch.id,
                    local_user_id=42,
                    verified_at=datetime.now(timezone.utc),
                ))
                db.commit()
                branch_id = branch.id

            branch_list = client.get("/api/organization-auth/branches", headers=headers)
            assert branch_list.status_code == 200, branch_list.text
            assert branch_list.json()["count"] == 1
            assert branch_list.json()["items"][0]["branch_code"] == "ACME-MAIN"

            grant_response = client.post(
                f"/api/organization-auth/branches/{branch_id}/access",
                headers=headers,
            )
            assert grant_response.status_code == 200, grant_response.text
            grant_payload = grant_response.json()
            assert grant_payload["expires_in"] == 600
            assert grant_payload["local_user_id"] == 42
            assert grant_payload["branch_access_token"].startswith("br_access_")
            with SessionLocal() as db:
                stored_grant = db.get(BranchAccessSession, grant_payload["grant_id"])
                assert stored_grant is not None
                assert stored_grant.token_hash != grant_payload["branch_access_token"]
                assert stored_grant.revoked_at is None

            missing_grant = client.post(
                "/api/organization-auth/branches/999999/access",
                headers=headers,
            )
            assert missing_grant.status_code == 403

            grant_revoked = client.delete(
                f"/api/organization-auth/branch-access/{grant_payload['grant_id']}",
                headers=headers,
            )
            assert grant_revoked.status_code == 200, grant_revoked.text

            profile = client.get("/api/organization-auth/me", headers=headers)
            assert profile.status_code == 200, profile.text
            assert profile.json()["user"]["group_role"] == "OWNER"
            assert profile.json()["user"]["mfa_enabled"] is True
            assert confirm.json()["refresh_token"]

            sessions = client.get("/api/organization-auth/sessions", headers=headers)
            assert sessions.status_code == 200, sessions.text
            assert len(sessions.json()["sessions"]) == 1
            session_id = sessions.json()["sessions"][0]["id"]

            rotated = client.post(
                "/api/organization-auth/refresh",
                json={"refresh_token": confirm.json()["refresh_token"]},
            )
            assert rotated.status_code == 200, rotated.text
            assert rotated.json()["refresh_token"] != confirm.json()["refresh_token"]

            replay = client.post(
                "/api/organization-auth/refresh",
                json={"refresh_token": confirm.json()["refresh_token"]},
            )
            assert replay.status_code == 401

            new_headers = {"Authorization": f"Bearer {rotated.json()['access_token']}"}
            old_access_denied = client.get("/api/organization-auth/me", headers=headers)
            assert old_access_denied.status_code == 401
            new_profile = client.get("/api/organization-auth/me", headers=new_headers)
            assert new_profile.status_code == 200, new_profile.text

            revoked = client.delete(
                f"/api/organization-auth/sessions/{session_id}",
                headers=new_headers,
            )
            assert revoked.status_code == 200, revoked.text
            denied = client.get("/api/organization-auth/me", headers=new_headers)
            assert denied.status_code == 401
    finally:
        control_app_module.app.dependency_overrides.pop(get_control_db, None)
        control_app_module.app.dependency_overrides.pop(get_redis, None)
        engine.dispose()
