import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.control_plane.models import (
    Branch,
    BranchAccessSession,
    BranchDepartmentAssignment,
    BranchMembership,
    BranchMembershipRole,
    BranchUserLink,
    HospitalGroup,
    OrganizationSession,
    OrganizationUser,
    TenantRegistry,
)


def test_organization_branch_grant_exchanges_once_and_is_branch_bound(
    client, multi_tenant_env
):
    control_factory = multi_tenant_env["control_session_factory"]
    tenant_engine = multi_tenant_env["tenant_engines"]["hms_default"]
    raw_grant = "br_access_" + secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)

    with control_factory() as control_db:
        registry = control_db.query(TenantRegistry).filter_by(
            subdomain_slug="default"
        ).one()
        group = HospitalGroup(
            code="EXCHANGE-GROUP",
            name="Exchange Test Hospital Group",
            status="ACTIVE",
        )
        control_db.add(group)
        control_db.flush()

        branch = Branch(
            group_id=group.id,
            tenant_registry_id=registry.id,
            code="HQ-HYD-01",
            name="Exchange Test Branch",
            status="ACTIVE",
        )
        org_user = OrganizationUser(
            group_id=group.id,
            email="doctor@default.com",
            email_normalized="doctor@default.com",
            full_name="Dr. Gregory House",
            group_role="STAFF",
            status="ACTIVE",
            email_verified_at=now,
        )
        control_db.add_all([branch, org_user])
        control_db.flush()

        org_session = OrganizationSession(
            organization_user_id=org_user.id,
            token_hash=hashlib.sha256(b"org-access-token").hexdigest(),
            expires_at=now + timedelta(minutes=10),
            refresh_expires_at=now + timedelta(days=1),
        )
        control_db.add(org_session)
        control_db.flush()

        with Session(tenant_engine) as tenant_db:
            from backend.domains.identity.models import User

            local_user = tenant_db.query(User).filter_by(
                email="doctor@default.com"
            ).one()
            local_user_id = local_user.id

        membership = BranchMembership(
            organization_user_id=org_user.id,
            branch_id=branch.id,
            group_id=group.id,
            status="ACTIVE",
        )
        control_db.add(membership)
        control_db.flush()
        control_db.add_all([
            BranchMembershipRole(
                membership_id=membership.id,
                role_code="ROLE_DOCTOR",
            ),
            BranchDepartmentAssignment(
                membership_id=membership.id,
                department_code="DEPT_GEN_MED",
            ),
            BranchUserLink(
                membership_id=membership.id,
                organization_user_id=org_user.id,
                branch_id=branch.id,
                local_user_id=local_user_id,
                verified_at=now,
            ),
        ])
        grant = BranchAccessSession(
            organization_session_id=org_session.id,
            membership_id=membership.id,
            token_hash=hashlib.sha256(raw_grant.encode("utf-8")).hexdigest(),
            expires_at=now + timedelta(minutes=10),
        )
        control_db.add(grant)
        control_db.commit()

    wrong_branch = client.post(
        "/api/auth/organization-branch-exchange",
        headers={
            "X-Hospital-Subdomain": "apollo",
            "X-Branch-Access-Token": raw_grant,
        },
    )
    assert wrong_branch.status_code == 401

    exchanged = client.post(
        "/api/auth/organization-branch-exchange",
        headers={
            "X-Hospital-Subdomain": "default",
            "X-Branch-Access-Token": raw_grant,
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    assert exchanged.json()["user"]["email"] == "doctor@default.com"
    assert exchanged.json()["branch"]["code"] == "HQ-HYD-01"
    assert exchanged.json()["access_token"]

    replay = client.post(
        "/api/auth/organization-branch-exchange",
        headers={
            "X-Hospital-Subdomain": "default",
            "X-Branch-Access-Token": raw_grant,
        },
    )
    assert replay.status_code == 401
