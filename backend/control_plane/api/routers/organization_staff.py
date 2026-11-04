"""Hospital-group owner administration of organization staff identities.

Branch membership and clinical authorization are deliberately separate from this
onboarding API. Activating a central identity does not grant access to any branch.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.control_plane.api.routers.organization_auth import require_organization_roles
from backend.control_plane.models import (
    ControlPlaneAuditLog,
    HospitalGroup,
    OrganizationInvitation,
    OrganizationUser,
)
from backend.core.config import settings
from backend.core.database import get_control_db
from backend.core.dependencies import RateLimiter
from backend.core.mailer import MailDeliveryError, send_email
from backend.domains.identity.passwords import pwd_context

router = APIRouter(prefix="/api/organization-staff", tags=["Hospital Staff Administration"])


class StaffInvitationRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class AcceptStaffInvitation(BaseModel):
    token: str = Field(min_length=40, max_length=256)
    password: str = Field(
        min_length=12,
        max_length=128,
        pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).+$",
    )


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _staff_payload(user: OrganizationUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "group_role": user.group_role,
        "status": user.status,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
    }


@router.get("")
def list_staff(
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    """List identities belonging only to the authenticated owner's hospital group."""
    users = db.execute(
        select(OrganizationUser)
        .where(
            OrganizationUser.group_id == identity["group_id"],
            OrganizationUser.group_role == "STAFF",
        )
        .order_by(OrganizationUser.full_name.asc(), OrganizationUser.id.asc())
    ).scalars().all()
    return {"items": [_staff_payload(user) for user in users], "count": len(users)}


@router.post(
    "/invitations",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(scope="organization_staff_invite", max_requests=20, window_seconds=3600))],
)
def invite_staff(
    payload: StaffInvitationRequest,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    group = db.execute(
        select(HospitalGroup)
        .where(HospitalGroup.id == identity["group_id"])
        .with_for_update()
    ).scalar_one_or_none()
    if not group or group.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="The hospital group is unavailable.")

    email_normalized = payload.email.strip().lower()
    existing = db.execute(
        select(OrganizationUser).where(
            OrganizationUser.group_id == group.id,
            OrganizationUser.email_normalized == email_normalized,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An identity with this email already exists in this hospital group.")

    pending = db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.group_id == group.id,
            OrganizationInvitation.email_normalized == email_normalized,
            OrganizationInvitation.invitation_type == "GROUP_STAFF",
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
            OrganizationInvitation.expires_at > datetime.now(timezone.utc),
        )
    ).scalar_one_or_none()
    if pending:
        raise HTTPException(status_code=409, detail="A valid staff invitation is already pending.")

    raw_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)
    user = OrganizationUser(
        group_id=group.id,
        email=payload.email,
        email_normalized=email_normalized,
        full_name=payload.full_name,
        group_role="STAFF",
        status="INVITED",
    )
    db.add(user)
    try:
        db.flush()
        invitation = OrganizationInvitation(
            group_id=group.id,
            organization_user_id=user.id,
            email_normalized=email_normalized,
            token_hash=_digest(raw_token),
            invitation_type="GROUP_STAFF",
            expires_at=expires_at,
        )
        db.add(invitation)
        db.add(ControlPlaneAuditLog(
            action="HOSPITAL_GROUP_STAFF_INVITED",
            target_slug="CONTROL_PLANE",
            actor=str(identity["user_id"]),
            details=f"Staff invitation issued for group {group.code}; email={email_normalized}.",
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A staff identity or invitation already exists.") from exc

    scheme = "https" if settings.is_production() else "http"
    invitation_url = (
        f"{scheme}://{settings.BASE_DOMAIN}/accept-organization-invitation"
        f"?token={raw_token}"
    )
    try:
        send_email(
            payload.email,
            f"Join {group.name}",
            (
                f"Hello {payload.full_name},\n\n"
                f"You have been invited to join {group.name} as a staff member.\n"
                f"Complete account setup within 24 hours using this link:\n{invitation_url}\n\n"
                "Your account will not have access to a hospital branch until the group owner assigns one.\n"
                "If you were not expecting this invitation, you can ignore this email."
            ),
        )
    except MailDeliveryError as exc:
        invitation_row = db.get(OrganizationInvitation, invitation.id)
        user_row = db.get(OrganizationUser, user.id)
        if invitation_row:
            invitation_row.revoked_at = datetime.now(timezone.utc)
        if user_row and user_row.status == "INVITED":
            db.delete(user_row)
        db.add(ControlPlaneAuditLog(
            action="HOSPITAL_GROUP_STAFF_INVITATION_DELIVERY_FAILED",
            target_slug="CONTROL_PLANE",
            actor=str(identity["user_id"]),
            details=f"Staff invitation delivery failed for group {group.code}; email={email_normalized}.",
        ))
        db.commit()
        raise HTTPException(status_code=503, detail="Invitation email could not be delivered; no active invitation remains.") from exc

    return {
        "status": "invitation_sent",
        "email": email_normalized,
        "expires_at": expires_at,
        "message": "The staff invitation has been emailed. The invitation token is never returned by this API.",
    }


@router.post(
    "/invitations/accept",
    dependencies=[Depends(RateLimiter(scope="organization_staff_invitation_accept", max_requests=5, window_seconds=900))],
)
def accept_staff_invitation(
    payload: AcceptStaffInvitation,
    db: Session = Depends(get_control_db),
):
    invitation = db.execute(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == _digest(payload.token))
        .with_for_update()
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not invitation or invitation.accepted_at or invitation.revoked_at:
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")
    expiry = invitation.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")

    group = db.get(HospitalGroup, invitation.group_id)
    user = db.get(OrganizationUser, invitation.organization_user_id)
    if (
        invitation.invitation_type != "GROUP_STAFF"
        or not group or group.status != "ACTIVE"
        or not user or user.status != "INVITED"
        or user.group_id != group.id
        or user.group_role != "STAFF"
        or user.email_normalized != invitation.email_normalized
    ):
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")

    user.password_hash = pwd_context.hash(payload.password)
    user.status = "ACTIVE"
    user.email_verified_at = now
    invitation.accepted_at = now
    db.add(ControlPlaneAuditLog(
        action="HOSPITAL_GROUP_STAFF_ACTIVATED",
        target_slug="CONTROL_PLANE",
        actor=str(user.id),
        details=f"Staff identity activated for hospital group {group.code}. No branch access was granted.",
    ))
    db.commit()
    return {
        "status": "activated",
        "user": _staff_payload(user),
        "message": "Your staff account is active. The hospital owner must assign your branch access separately.",
    }


# Branch assignment endpoints. These store the organization's authorization intent.
# They do not mint a branch-local JWT or mutate legacy UserRole rows; branch-session
# enforcement is a separate migration step so legacy login is not silently changed.
from sqlalchemy.orm import sessionmaker

from backend.control_plane.models import (
    Branch,
    BranchDepartmentAssignment,
    BranchMembership,
    BranchMembershipRole,
    BranchUserLink,
    BranchAccessSession,
    OrganizationSession,
    TenantRegistry,
)
from backend.core.database import tenant_engine_pool
from backend.domains.identity.models import Department, Role, User, UserStatusEnum


class BranchAssignmentRequest(BaseModel):
    local_user_id: int = Field(gt=0)
    role_codes: list[str] = Field(min_length=1, max_length=30)
    department_codes: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("role_codes", "department_codes")
    @classmethod
    def normalize_codes(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 100 for value in cleaned):
            raise ValueError("Role and department codes must be non-empty and at most 100 characters.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Duplicate role or department codes are not allowed.")
        return cleaned


class MembershipStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
            raise ValueError("Status must be ACTIVE, SUSPENDED, or REVOKED.")
        return normalized


def _branch_for_group(db: Session, group_id: int, branch_id: int) -> tuple[Branch, TenantRegistry]:
    row = db.execute(
        select(Branch, TenantRegistry)
        .join(TenantRegistry, TenantRegistry.id == Branch.tenant_registry_id)
        .where(
            Branch.id == branch_id,
            Branch.group_id == group_id,
            Branch.status == "ACTIVE",
            TenantRegistry.is_active.is_(True),
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Active branch not found in your hospital group.")
    return row[0], row[1]


@router.get("/branches")
def list_group_branches(
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    rows = db.execute(
        select(Branch)
        .where(Branch.group_id == identity["group_id"], Branch.status == "ACTIVE")
        .order_by(Branch.name.asc(), Branch.id.asc())
    ).scalars().all()
    return {
        "items": [
            {"id": branch.id, "code": branch.code, "name": branch.name, "status": branch.status}
            for branch in rows
        ],
        "count": len(rows),
    }


@router.get("/branches/{branch_id}/catalogue")
def get_branch_catalogue(
    branch_id: int,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    branch, registry = _branch_for_group(db, identity["group_id"], branch_id)
    LocalSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=tenant_engine_pool.get_engine(registry.db_name),
    )
    try:
        with LocalSession() as local_db:
            roles = local_db.execute(
                select(Role).order_by(Role.name.asc(), Role.code.asc())
            ).scalars().all()
            departments = local_db.execute(
                select(Department)
                .where(Department.is_active.is_(True))
                .order_by(Department.name.asc(), Department.code.asc())
            ).scalars().all()
            return {
                "branch": {"id": branch.id, "code": branch.code, "name": branch.name},
                "roles": [
                    {"code": role.code, "name": role.name, "description": role.description}
                    for role in roles
                ],
                "departments": [
                    {"code": department.code, "name": department.name}
                    for department in departments
                ],
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Branch role catalogue is temporarily unavailable.") from exc


@router.post("/{organization_user_id}/branches", status_code=status.HTTP_201_CREATED)
def assign_staff_to_branch(
    organization_user_id: int,
    branch_id: int,
    payload: BranchAssignmentRequest,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    now = datetime.now(timezone.utc)
    staff = db.execute(
        select(OrganizationUser)
        .where(
            OrganizationUser.id == organization_user_id,
            OrganizationUser.group_id == identity["group_id"],
            OrganizationUser.group_role == "STAFF",
            OrganizationUser.status == "ACTIVE",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Active staff identity not found in your hospital group.")

    branch, registry = _branch_for_group(db, identity["group_id"], branch_id)
    LocalSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=tenant_engine_pool.get_engine(registry.db_name),
    )
    try:
        with LocalSession() as local_db:
            local_user = local_db.get(User, payload.local_user_id)
            if (
                not local_user
                or local_user.status != UserStatusEnum.ACTIVE
                or local_user.email.strip().lower() != staff.email_normalized
                or " ".join(local_user.full_name.split()).casefold()
                != " ".join(staff.full_name.split()).casefold()
            ):
                raise HTTPException(
                    status_code=409,
                    detail="The selected branch-local user does not match this staff identity. No automatic email-only linking is allowed.",
                )

            role_rows = local_db.execute(
                select(Role).where(Role.code.in_(payload.role_codes))
            ).scalars().all()
            role_map = {role.code: role for role in role_rows}
            if set(role_map) != set(payload.role_codes):
                raise HTTPException(status_code=422, detail="One or more role codes do not exist in this branch.")

            department_rows = []
            if payload.department_codes:
                department_rows = local_db.execute(
                    select(Department).where(
                        Department.code.in_(payload.department_codes),
                        Department.is_active.is_(True),
                    )
                ).scalars().all()
            department_map = {department.code: department for department in department_rows}
            if set(department_map) != set(payload.department_codes):
                raise HTTPException(status_code=422, detail="One or more department codes do not exist or are inactive in this branch.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not verify the selected branch-local identity and catalogue.") from exc

    existing = db.execute(
        select(BranchMembership)
        .where(
            BranchMembership.organization_user_id == staff.id,
            BranchMembership.branch_id == branch.id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing:
        if existing.status == "ACTIVE":
            raise HTTPException(status_code=409, detail="Staff already has an active membership in this branch.")
        if existing.status == "REVOKED":
            raise HTTPException(status_code=409, detail="This membership was revoked. Revoked memberships are terminal; contact support to correct an accidental revocation.")
        raise HTTPException(status_code=409, detail="This membership is suspended. Reactivate it through the membership status endpoint before changing its assignment.")

    try:
        membership = BranchMembership(
            organization_user_id=staff.id,
            branch_id=branch.id,
            group_id=identity["group_id"],
            status="ACTIVE",
        )
        db.add(membership)
        db.flush()

        for role_code in payload.role_codes:
            db.add(BranchMembershipRole(membership_id=membership.id, role_code=role_code))
        for department_code in payload.department_codes:
            db.add(BranchDepartmentAssignment(
                membership_id=membership.id,
                department_code=department_code,
            ))

        link = db.execute(
            select(BranchUserLink)
            .where(BranchUserLink.membership_id == membership.id)
            .with_for_update()
        ).scalar_one_or_none()
        if link and link.local_user_id != payload.local_user_id:
            raise HTTPException(status_code=409, detail="This membership is already linked to a different branch-local user.")
        if link:
            link.verified_at = now
        else:
            db.add(BranchUserLink(
                membership_id=membership.id,
                organization_user_id=staff.id,
                branch_id=branch.id,
                local_user_id=payload.local_user_id,
                verified_at=now,
            ))

        db.add(ControlPlaneAuditLog(
            action="HOSPITAL_GROUP_STAFF_BRANCH_ASSIGNED",
            target_slug="CONTROL_PLANE",
            actor=str(identity["user_id"]),
            details=(
                f"Staff {staff.id} assigned to branch {branch.code}; "
                f"local_user_id={payload.local_user_id}; roles={','.join(payload.role_codes)}; "
                f"departments={','.join(payload.department_codes)}."
            ),
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The branch membership or local-user link conflicts with an existing assignment.") from exc

    return {
        "membership_id": membership.id,
        "organization_user_id": staff.id,
        "branch": {"id": branch.id, "code": branch.code, "name": branch.name},
        "local_user_id": payload.local_user_id,
        "roles": payload.role_codes,
        "departments": payload.department_codes,
        "status": membership.status,
        "clinical_access_enabled": False,
        "message": "Branch assignment is recorded. Clinical access remains governed by the branch-session integration and is not enabled by this assignment alone.",
    }


@router.patch("/memberships/{membership_id}/status")
def update_membership_status(
    membership_id: int,
    payload: MembershipStatusRequest,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    membership = db.execute(
        select(BranchMembership)
        .where(
            BranchMembership.id == membership_id,
            BranchMembership.group_id == identity["group_id"],
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Branch membership not found in your hospital group.")
    if membership.status == "REVOKED" and payload.status != "REVOKED":
        raise HTTPException(status_code=409, detail="A revoked membership cannot be reactivated; create a new assignment.")
    if payload.status == "ACTIVE":
        staff = db.get(OrganizationUser, membership.organization_user_id)
        branch = db.get(Branch, membership.branch_id)
        if not staff or staff.status != "ACTIVE" or not branch or branch.status != "ACTIVE":
            raise HTTPException(status_code=409, detail="Staff identity and branch must both be active.")
    membership.status = payload.status
    if payload.status in {"SUSPENDED", "REVOKED"}:
        active_grants = db.execute(
            select(BranchAccessSession)
            .join(OrganizationSession, OrganizationSession.id == BranchAccessSession.organization_session_id)
            .where(
                BranchAccessSession.membership_id == membership.id,
                BranchAccessSession.revoked_at.is_(None),
                OrganizationSession.revoked_at.is_(None),
            )
            .with_for_update()
        ).scalars().all()
        for grant in active_grants:
            grant.revoked_at = datetime.now(timezone.utc)
    if payload.status == "REVOKED":
        membership.revoked_at = datetime.now(timezone.utc)
    elif payload.status == "ACTIVE":
        membership.revoked_at = None

    db.add(ControlPlaneAuditLog(
        action=f"HOSPITAL_GROUP_STAFF_BRANCH_{payload.status}",
        target_slug="CONTROL_PLANE",
        actor=str(identity["user_id"]),
        details=f"Membership {membership.id} status changed to {payload.status}.",
    ))
    db.commit()
    return {"membership_id": membership.id, "status": membership.status}



class StaffStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"ACTIVE", "SUSPENDED", "DEACTIVATED"}:
            raise ValueError("Status must be ACTIVE, SUSPENDED, or DEACTIVATED.")
        return normalized


@router.patch("/{organization_user_id}/status")
def update_staff_status(
    organization_user_id: int,
    payload: StaffStatusRequest,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    staff = db.execute(
        select(OrganizationUser)
        .where(
            OrganizationUser.id == organization_user_id,
            OrganizationUser.group_id == identity["group_id"],
            OrganizationUser.group_role == "STAFF",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff identity not found in your hospital group.")
    if staff.status == "DEACTIVATED" and payload.status != "DEACTIVATED":
        raise HTTPException(status_code=409, detail="A deactivated staff identity cannot be reactivated.")
    if staff.status == "INVITED" and payload.status == "ACTIVE":
        raise HTTPException(status_code=409, detail="The staff member must accept their invitation before activation.")

    previous_status = staff.status
    staff.status = payload.status
    now = datetime.now(timezone.utc)
    if payload.status in {"SUSPENDED", "DEACTIVATED"}:
        sessions = db.execute(
            select(OrganizationSession).where(
                OrganizationSession.organization_user_id == staff.id,
                OrganizationSession.revoked_at.is_(None),
            )
        ).scalars().all()
        for session in sessions:
            session.revoked_at = now
            branch_sessions = db.execute(
                select(BranchAccessSession).where(
                    BranchAccessSession.organization_session_id == session.id,
                    BranchAccessSession.revoked_at.is_(None),
                )
            ).scalars().all()
            for branch_session in branch_sessions:
                branch_session.revoked_at = now

    db.add(ControlPlaneAuditLog(
        action=f"HOSPITAL_GROUP_STAFF_{payload.status}",
        target_slug="CONTROL_PLANE",
        actor=str(identity["user_id"]),
        details=f"Staff identity {staff.id} changed from {previous_status} to {payload.status}; active sessions revoked where applicable.",
    ))
    db.commit()
    return {
        "organization_user_id": staff.id,
        "previous_status": previous_status,
        "status": staff.status,
        "sessions_revoked": payload.status in {"SUSPENDED", "DEACTIVATED"},
    }



@router.get("/{organization_user_id}/branches")
def list_staff_branch_assignments(
    organization_user_id: int,
    identity: dict = Depends(require_organization_roles("OWNER")),
    db: Session = Depends(get_control_db),
):
    staff = db.execute(
        select(OrganizationUser).where(
            OrganizationUser.id == organization_user_id,
            OrganizationUser.group_id == identity["group_id"],
            OrganizationUser.group_role == "STAFF",
        )
    ).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff identity not found in your hospital group.")

    memberships = db.execute(
        select(BranchMembership, Branch)
        .join(Branch, Branch.id == BranchMembership.branch_id)
        .where(
            BranchMembership.organization_user_id == staff.id,
            BranchMembership.group_id == identity["group_id"],
        )
        .order_by(Branch.name.asc(), Branch.id.asc())
    ).all()

    items = []
    for membership, branch in memberships:
        roles = db.execute(
            select(BranchMembershipRole.role_code)
            .where(BranchMembershipRole.membership_id == membership.id)
            .order_by(BranchMembershipRole.role_code.asc())
        ).scalars().all()
        departments = db.execute(
            select(BranchDepartmentAssignment.department_code)
            .where(BranchDepartmentAssignment.membership_id == membership.id)
            .order_by(BranchDepartmentAssignment.department_code.asc())
        ).scalars().all()
        link = db.execute(
            select(BranchUserLink).where(BranchUserLink.membership_id == membership.id)
        ).scalar_one_or_none()
        items.append({
            "membership_id": membership.id,
            "branch": {"id": branch.id, "code": branch.code, "name": branch.name},
            "status": membership.status,
            "local_user_id": link.local_user_id if link else None,
            "identity_link_verified": bool(link and link.verified_at),
            "roles": roles,
            "departments": departments,
        })
    return {"organization_user_id": staff.id, "items": items, "count": len(items)}
