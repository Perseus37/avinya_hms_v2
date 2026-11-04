from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.control_plane.models import (
    Branch,
    BranchAccessSession,
    BranchMembership,
    BranchMembershipRole,
    BranchDepartmentAssignment,
    BranchUserLink,
    ControlBase,
    HospitalGroup,
    OrganizationSession,
    OrganizationUser,
    TenantRegistry,
    DeploymentModeEnum,
)
from backend.core import dependencies
from backend.core.database import Base, TenantContext
from backend.domains.identity.models import Department, Permission, Role, User, UserRole, UserStatusEnum


@pytest.fixture
def branch_grant_environment(monkeypatch):
    control_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tenant_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    ControlBase.metadata.create_all(control_engine)
    Base.metadata.create_all(tenant_engine)
    ControlSession = sessionmaker(bind=control_engine, expire_on_commit=False)
    TenantSession = sessionmaker(bind=tenant_engine, expire_on_commit=False)
    monkeypatch.setattr(dependencies, "ControlSessionLocal", ControlSession)

    now = datetime.now(timezone.utc)
    with ControlSession() as control:
        group = HospitalGroup(code="GRANT-TEST", name="Grant Test Hospital", status="ACTIVE")
        control.add(group)
        control.flush()
        registry = TenantRegistry(
            hospital_name="Grant Test Branch",
            branch_code="GRANT-BR-01",
            subdomain_slug="grant-test",
            db_name="hms_grant_test",
            admin_email="admin@grant.example",
            jwt_secret_key="test-secret",
            backup_encryption_key="test-backup-key",
            deployment_mode=DeploymentModeEnum.CLOUD,
            is_active=True,
        )
        control.add(registry)
        control.flush()
        branch = Branch(
            group_id=group.id,
            tenant_registry_id=registry.id,
            code=registry.branch_code,
            name=registry.hospital_name,
            status="ACTIVE",
        )
        control.add(branch)
        control.flush()
        org_user = OrganizationUser(
            group_id=group.id,
            email="doctor@grant.example",
            email_normalized="doctor@grant.example",
            full_name="Test Doctor",
            group_role="STAFF",
            status="ACTIVE",
        )
        control.add(org_user)
        control.flush()
        membership = BranchMembership(
            organization_user_id=org_user.id,
            branch_id=branch.id,
            group_id=group.id,
            status="ACTIVE",
        )
        control.add(membership)
        control.flush()
        link = BranchUserLink(
            membership_id=membership.id,
            organization_user_id=org_user.id,
            branch_id=branch.id,
            local_user_id=1,
            verified_at=now,
        )
        org_session = OrganizationSession(
            organization_user_id=org_user.id,
            token_hash="a" * 64,
            expires_at=now + timedelta(minutes=20),
        )
        control.add_all([link, org_session])
        control.flush()
        grant = BranchAccessSession(
            organization_session_id=org_session.id,
            membership_id=membership.id,
            token_hash=dependencies.hashlib.sha256(b"br_access_test-secret-token").hexdigest(),
            expires_at=now + timedelta(minutes=10),
        )
        control.add(grant)
        control.add(BranchMembershipRole(membership_id=membership.id, role_code="DOCTOR"))
        control.add(BranchDepartmentAssignment(membership_id=membership.id, department_code="CARDIOLOGY"))
        control.commit()

    with TenantSession() as tenant_db:
        department = Department(code="CARDIOLOGY", name="Cardiology")
        role = Role(code="DOCTOR", name="Doctor")
        local_admin = Role(code="LOCAL_ADMIN", name="Local Admin")
        elevated_permission = Permission(
            code="patient:delete",
            description="Delete patient",
            module="patients",
        )
        local_admin.permissions.append(elevated_permission)
        user = User(
            login_id="doctor-grant",
            email="doctor@grant.example",
            hashed_password="not-used",
            full_name="Test Doctor",
            status=UserStatusEnum.ACTIVE,
        )
        user.roles.extend([role, local_admin])
        tenant_db.add(user)
        tenant_db.commit()
        local_user_id = user.id
        assert local_user_id == 1

    tenant_context = TenantContext(
        subdomain_slug="grant-test",
        branch_code="GRANT-BR-01",
        hospital_name="Grant Test Branch",
        db_name="hms_grant_test",
        jwt_secret_key="unused",
    )
    yield ControlSession, TenantSession, tenant_context, grant.id
    control_engine.dispose()
    tenant_engine.dispose()


def test_branch_grant_authenticates_linked_local_user_and_scopes_roles(
    branch_grant_environment,
):
    _, TenantSession, tenant_context, _ = branch_grant_environment
    with TenantSession() as tenant_db:
        user = dependencies._authenticate_branch_access_token(
            "br_access_test-secret-token", tenant_context, tenant_db
        )
        assert user.id == 1
        assert tenant_db.info["central_branch_role_codes"] == frozenset({"DOCTOR"})
        assert tenant_db.info["central_branch_membership_id"] > 0


def test_branch_grant_cannot_be_reused_on_another_branch(branch_grant_environment):
    _, TenantSession, tenant_context, _ = branch_grant_environment
    wrong_branch = TenantContext(
        subdomain_slug="another-branch",
        branch_code="OTHER-BR-01",
        hospital_name="Other Branch",
        db_name="hms_other",
        jwt_secret_key="unused",
    )
    with TenantSession() as tenant_db:
        with pytest.raises(HTTPException) as exc:
            dependencies._authenticate_branch_access_token(
                "br_access_test-secret-token", wrong_branch, tenant_db
            )
    assert exc.value.status_code == 401


def test_branch_grant_rejects_revoked_grant(branch_grant_environment):
    ControlSession, TenantSession, tenant_context, grant_id = branch_grant_environment
    with ControlSession() as control:
        grant = control.get(BranchAccessSession, grant_id)
        grant.revoked_at = datetime.now(timezone.utc)
        control.commit()
    with TenantSession() as tenant_db:
        with pytest.raises(HTTPException) as exc:
            dependencies._authenticate_branch_access_token(
                "br_access_test-secret-token", tenant_context, tenant_db
            )
    assert exc.value.status_code == 401



def test_branch_grant_rejects_local_superuser(branch_grant_environment):
    _, TenantSession, tenant_context, _ = branch_grant_environment
    with TenantSession() as tenant_db:
        user = tenant_db.get(User, 1)
        user.is_superuser = True
        tenant_db.commit()
        with pytest.raises(HTTPException) as exc:
            dependencies._authenticate_branch_access_token(
                "br_access_test-secret-token", tenant_context, tenant_db
            )
    assert exc.value.status_code == 401


def test_branch_grant_cannot_use_unassigned_local_role_permissions(
    branch_grant_environment,
):
    _, TenantSession, tenant_context, _ = branch_grant_environment
    with TenantSession() as tenant_db:
        user = dependencies._authenticate_branch_access_token(
            "br_access_test-secret-token", tenant_context, tenant_db
        )
        assert {role.code for role in user.roles} == {"DOCTOR"}
        assert not dependencies.user_has_permission(
            tenant_db, user, "patient:delete"
        )



def test_department_access_requires_both_local_and_central_assignment(
    branch_grant_environment,
):
    _, TenantSession, tenant_context, _ = branch_grant_environment
    with TenantSession() as tenant_db:
        user = dependencies._authenticate_branch_access_token(
            "br_access_test-secret-token", tenant_context, tenant_db
        )
        department = tenant_db.query(Department).filter_by(code="CARDIOLOGY").one()
        assert dependencies.user_has_department_access(
            tenant_db, user, department.id
        )
        assert not dependencies.user_has_department_access(
            tenant_db, user, department.id + 1000
        )
