from typing import Any
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.control_plane.models import (
    Branch,
    ControlPlaneAuditLog,
    HospitalGroup,
    OrganizationInvitation,
    OrganizationUser,
    TenantRegistry,
)
from backend.control_plane.services.auth import require_operator_role
from backend.core.config import settings
from backend.core.dependencies import RateLimiter
from backend.core.mailer import MailDeliveryError, send_email
from backend.domains.identity.passwords import pwd_context
from backend.core.database import get_control_db


router = APIRouter(prefix="/api/organization-groups", tags=["Hospital Group Administration"])


class HospitalGroupCreate(BaseModel):
    code: str = Field(min_length=2, max_length=63, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class BranchRegistrationRequest(BaseModel):
    tenant_registry_id: int = Field(gt=0)



class OwnerInvitationRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class AcceptOrganizationInvitation(BaseModel):
    token: str = Field(min_length=40, max_length=256)
    password: str = Field(min_length=12, max_length=128, pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).+$")


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _group_payload(group: HospitalGroup) -> dict[str, Any]:
    return {
        "id": group.id,
        "code": group.code,
        "name": group.name,
        "status": group.status,
        "created_at": group.created_at,
    }


def _branch_payload(branch: Branch, tenant: TenantRegistry) -> dict[str, Any]:
    return {
        "id": branch.id,
        "group_id": branch.group_id,
        "tenant_registry_id": branch.tenant_registry_id,
        "code": branch.code,
        "name": branch.name,
        "status": branch.status,
        "subdomain_slug": tenant.subdomain_slug,
        "tenant_active": tenant.is_active,
        "created_at": branch.created_at,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_hospital_group(
    payload: HospitalGroupCreate,
    db: Session = Depends(get_control_db),
    _: str = Depends(require_operator_role("superadmin")),
):
    existing = db.execute(
        select(HospitalGroup).where(HospitalGroup.code == payload.code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Hospital group code is already registered.")

    group = HospitalGroup(code=payload.code, name=payload.name, status="ACTIVE")
    db.add(group)
    try:
        db.flush()
        db.add(
            ControlPlaneAuditLog(
                action="HOSPITAL_GROUP_CREATED",
                target_slug="CONTROL_PLANE",
                details=f"Hospital group {group.code} (id={group.id}) created.",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Hospital group code is already registered.") from exc
    db.refresh(group)
    return _group_payload(group)


@router.get("")
def list_hospital_groups(
    db: Session = Depends(get_control_db),
    _: str = Depends(require_operator_role("superadmin", "ops", "support", "viewer")),
):
    groups = db.execute(
        select(HospitalGroup).order_by(HospitalGroup.name.asc(), HospitalGroup.id.asc())
    ).scalars().all()
    return {"items": [_group_payload(group) for group in groups], "count": len(groups)}


@router.get("/{group_id}")
def get_hospital_group(
    group_id: int,
    db: Session = Depends(get_control_db),
    _: str = Depends(require_operator_role("superadmin", "ops", "support", "viewer")),
):
    group = db.get(HospitalGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Hospital group not found.")
    branches = db.execute(
        select(Branch, TenantRegistry)
        .join(TenantRegistry, TenantRegistry.id == Branch.tenant_registry_id)
        .where(Branch.group_id == group.id)
        .order_by(Branch.name.asc(), Branch.id.asc())
    ).all()
    return {
        **_group_payload(group),
        "branches": [_branch_payload(branch, tenant) for branch, tenant in branches],
        "branch_count": len(branches),
    }


@router.post("/{group_id}/branches", status_code=status.HTTP_201_CREATED)
def register_existing_branch(
    group_id: int,
    payload: BranchRegistrationRequest,
    db: Session = Depends(get_control_db),
    _: str = Depends(require_operator_role("superadmin", "ops")),
):
    group = db.get(HospitalGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Hospital group not found.")
    if group.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Branches can only be registered to an active hospital group.")

    tenant = db.get(TenantRegistry, payload.tenant_registry_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Existing branch tenant was not found.")
    if not tenant.is_active:
        raise HTTPException(status_code=409, detail="Inactive branch tenants cannot be newly registered.")

    existing = db.execute(
        select(Branch).where(Branch.tenant_registry_id == tenant.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This branch tenant is already assigned to a hospital group.",
        )

    branch = Branch(
        group_id=group.id,
        tenant_registry_id=tenant.id,
        code=tenant.branch_code,
        name=tenant.hospital_name,
        status="ACTIVE",
    )
    db.add(branch)
    try:
        db.flush()
        db.add(
            ControlPlaneAuditLog(
                action="HOSPITAL_GROUP_BRANCH_REGISTERED",
                target_slug=tenant.subdomain_slug,
                details=(
                    f"Existing branch {tenant.branch_code} (tenant_registry_id={tenant.id}) "
                    f"registered under hospital group {group.code} (id={group.id})."
                ),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Branch registration conflicts with an existing group assignment.",
        ) from exc
    db.refresh(branch)
    return _branch_payload(branch, tenant)


@router.post(
    "/{group_id}/owner-invitations",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(scope="organization_owner_invite", max_requests=5, window_seconds=3600))],
)
def invite_initial_group_owner(
    group_id: int,
    payload: OwnerInvitationRequest,
    db: Session = Depends(get_control_db),
    _: str = Depends(require_operator_role("superadmin")),
):
    """Vendor bootstrap only: issue the first owner invitation, not a staff permission."""
    group = db.execute(
        select(HospitalGroup).where(HospitalGroup.id == group_id).with_for_update()
    ).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Hospital group not found.")
    if group.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active hospital groups can receive an owner.")

    owner_exists = db.execute(
        select(OrganizationUser.id).where(
            OrganizationUser.group_id == group.id,
            OrganizationUser.group_role == "OWNER",
            OrganizationUser.status == "ACTIVE",
        )
    ).first()
    if owner_exists:
        raise HTTPException(status_code=409, detail="This hospital group already has an active owner.")

    email_normalized = payload.email.strip().lower()
    existing_user = db.execute(
        select(OrganizationUser).where(
            OrganizationUser.group_id == group.id,
            OrganizationUser.email_normalized == email_normalized,
        )
    ).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=409, detail="An identity with this email already exists in this group.")

    pending = db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.group_id == group.id,
            OrganizationInvitation.email_normalized == email_normalized,
            OrganizationInvitation.invitation_type == "GROUP_OWNER",
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
            OrganizationInvitation.expires_at > datetime.now(timezone.utc),
        )
    ).scalar_one_or_none()
    if pending:
        raise HTTPException(status_code=409, detail="A valid owner invitation is already pending.")

    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    user = OrganizationUser(
        group_id=group.id,
        email=payload.email,
        email_normalized=email_normalized,
        full_name=payload.full_name,
        group_role="OWNER",
        status="INVITED",
    )
    db.add(user)
    try:
        db.flush()
        invitation = OrganizationInvitation(
            group_id=group.id,
            organization_user_id=user.id,
            email_normalized=email_normalized,
            token_hash=_token_digest(raw_token),
            invitation_type="GROUP_OWNER",
            expires_at=expires_at,
        )
        db.add(invitation)
        db.add(ControlPlaneAuditLog(
            action="HOSPITAL_GROUP_OWNER_INVITED",
            target_slug="CONTROL_PLANE",
            details=f"Initial owner invitation issued for group {group.code}; invitation_id pending commit.",
        ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An owner invitation or identity already exists.") from exc

    scheme = "https" if settings.is_production() else "http"
    invitation_url = (
        f"{scheme}://{settings.BASE_DOMAIN}/accept-organization-invitation"
        f"?token={raw_token}"
    )
    try:
        send_email(
            payload.email,
            f"Become the Hospital Group Owner - {group.name}",
            (
                f"Hello {payload.full_name},\n\n"
                f"You have been invited to become the initial owner of {group.name}.\n"
                f"Complete setup within 24 hours using this link:\n{invitation_url}\n\n"
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
            action="HOSPITAL_GROUP_OWNER_INVITATION_DELIVERY_FAILED",
            target_slug="CONTROL_PLANE",
            details=f"Owner invitation delivery failed for group {group.code}.",
        ))
        db.commit()
        raise HTTPException(status_code=503, detail="Invitation email could not be delivered; no active invitation remains.") from exc

    return {
        "status": "invitation_sent",
        "email": email_normalized,
        "expires_at": expires_at,
        "message": "The first owner invitation has been emailed. The invitation token is never returned by this API.",
    }


@router.post(
    "/invitations/accept",
    dependencies=[Depends(RateLimiter(scope="organization_invitation_accept", max_requests=5, window_seconds=900))],
)
def accept_organization_invitation(
    payload: AcceptOrganizationInvitation,
    db: Session = Depends(get_control_db),
):
    invitation = db.execute(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == _token_digest(payload.token))
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
        not group or group.status != "ACTIVE" or not user
        or user.status != "INVITED"
        or user.email_normalized != invitation.email_normalized
        or invitation.invitation_type != "GROUP_OWNER"
        or user.group_role != "OWNER"
    ):
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")

    active_owner = db.execute(
        select(OrganizationUser.id).where(
            OrganizationUser.group_id == group.id,
            OrganizationUser.group_role == "OWNER",
            OrganizationUser.status == "ACTIVE",
        )
    ).first()
    if active_owner:
        invitation.revoked_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="This hospital group already has an active owner.")

    user.password_hash = pwd_context.hash(payload.password)
    user.status = "ACTIVE"
    user.email_verified_at = now
    invitation.accepted_at = now
    db.add(ControlPlaneAuditLog(
        action="HOSPITAL_GROUP_OWNER_ACTIVATED",
        target_slug="CONTROL_PLANE",
        details=f"Initial owner activated for hospital group {group.code}.",
    ))
    db.commit()
    return {
        "status": "activated",
        "group": {"id": group.id, "code": group.code, "name": group.name},
        "message": "Your Hospital Group Owner account is active. Sign in to continue.",
    }
