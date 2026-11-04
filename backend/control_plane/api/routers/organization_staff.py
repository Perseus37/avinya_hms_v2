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
