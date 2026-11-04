import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.control_plane import app as control_app_module
from backend.control_plane.api.routers import organization_auth, organization_staff
from backend.control_plane.models import ControlBase, HospitalGroup, OrganizationUser
from backend.core.database import get_control_db
from backend.core.dependencies import get_redis


def test_owner_invites_staff_and_staff_activation_grants_no_branch_membership(monkeypatch):
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
        owner = OrganizationUser(
            group_id=group.id,
            email="owner@acme.example",
            email_normalized="owner@acme.example",
            full_name="Acme Owner",
            group_role="OWNER",
            status="ACTIVE",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(owner)
        db.commit()
        owner_id = owner.id
        group_id = group.id

    def override_get_control_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    class TestRedis:
        def get(self, key):
            return None

        def set(self, key, value, ex=None):
            return True

    monkeypatch.setattr(control_app_module, "ControlSessionLocal", SessionLocal)
    control_app_module.app.dependency_overrides[get_control_db] = override_get_control_db
    control_app_module.app.dependency_overrides[get_redis] = lambda: TestRedis()
    control_app_module.app.dependency_overrides[organization_auth._current_identity] = lambda: {
        "user_id": owner_id,
        "group_id": group_id,
        "session_id": 1,
        "token_hash": "test-token-hash",
    }

    delivered = {}
    monkeypatch.setattr(
        organization_staff,
        "send_email",
        lambda recipient, subject, body: delivered.update(
            {"recipient": recipient, "subject": subject, "body": body}
        ),
    )

    try:
        with TestClient(control_app_module.app) as client:
            invite = client.post(
                "/api/organization-staff/invitations",
                json={"email": "doctor@acme.example", "full_name": "Dr. Test Doctor"},
            )
            assert invite.status_code == 202, invite.text
            assert "token" not in invite.json()
            assert delivered["recipient"] == "doctor@acme.example"
            match = re.search(r"token=([A-Za-z0-9_-]+)", delivered["body"])
            assert match
            token = match.group(1)

            listing = client.get("/api/organization-staff")
            assert listing.status_code == 200, listing.text
            assert listing.json()["count"] == 1
            assert listing.json()["items"][0]["status"] == "INVITED"

            # A staff token must not be accepted by the vendor-only owner bootstrap route.
            wrong_acceptor = client.post(
                "/api/organization-groups/invitations/accept",
                json={"token": token, "password": "SecureStaffPass123!"},
            )
            assert wrong_acceptor.status_code == 400

            accepted = client.post(
                "/api/organization-staff/invitations/accept",
                json={"token": token, "password": "SecureStaffPass123!"},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["status"] == "activated"
            assert accepted.json()["user"]["status"] == "ACTIVE"

            replay = client.post(
                "/api/organization-staff/invitations/accept",
                json={"token": token, "password": "SecureStaffPass123!"},
            )
            assert replay.status_code == 400

            with SessionLocal() as db:
                staff = db.query(OrganizationUser).filter_by(
                    group_id=group_id,
                    email_normalized="doctor@acme.example",
                ).one()
                assert staff.group_role == "STAFF"
                assert staff.status == "ACTIVE"
                assert db.query(organization_staff.BranchMembership).count() == 0
    finally:
        control_app_module.app.dependency_overrides.pop(get_control_db, None)
        control_app_module.app.dependency_overrides.pop(get_redis, None)
        control_app_module.app.dependency_overrides.pop(organization_auth._current_identity, None)
        engine.dispose()
