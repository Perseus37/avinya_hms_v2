"""Hospital-group authentication, MFA and central organization sessions.

This identity plane is separate from vendor operators and branch-local clinical users.
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.control_plane.models import (
    Branch,
    BranchAccessSession,
    BranchDepartmentAssignment,
    BranchMembership,
    BranchMembershipRole,
    BranchUserLink,
    ControlPlaneAuditLog,
    HospitalGroup,
    OrganizationSession,
    OrganizationUser,
    TenantRegistry,
)
from backend.core.config import settings
from backend.core.database import ControlSessionLocal, get_control_db
from backend.core.dependencies import RateLimiter
from backend.domains.identity.passwords import pwd_context
from backend.security.envelope import decrypt_tenant_secret, encrypt_tenant_secret
from backend.security.totp import matching_totp_counter

router = APIRouter(prefix="/api/organization-auth", tags=["Hospital Organization Identity"])
_LOGIN_LIMIT = RateLimiter(scope="auth_login_organization", max_requests=10, window_seconds=60)
_MFA_LIMIT = RateLimiter(scope="auth_mfa_organization", max_requests=5, window_seconds=300)
_DUMMY_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKd.RvvJ8hYjT.W"


class OrganizationLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    group_code: str = Field(min_length=2, max_length=63)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("group_code", mode="before")
    @classmethod
    def normalize_group_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class MfaChallenge(BaseModel):
    mfa_token: str = Field(min_length=32, max_length=4096)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=256)


class MfaVerification(MfaChallenge):
    code: str = Field(pattern=r"^[0-9]{6}$")


def _challenge_token(user: OrganizationUser, purpose: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "group_id": user.group_id,
            "purpose": purpose,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": secrets.token_urlsafe(16),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _load_challenge(db: Session, token: str, purpose: str) -> OrganizationUser:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge.") from exc
    subject = claims.get("sub")
    group_id = claims.get("group_id")
    if (
        claims.get("purpose") != purpose
        or not isinstance(subject, str)
        or not subject.isdecimal()
        or not isinstance(group_id, int)
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge.")
    user = db.execute(
        select(OrganizationUser)
        .where(
            OrganizationUser.id == int(subject),
            OrganizationUser.group_id == group_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not user or user.status != "ACTIVE":
        raise HTTPException(status_code=401, detail="Organization account is unavailable.")
    group = db.get(HospitalGroup, group_id)
    if not group or group.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Hospital group is unavailable.")
    return user


def _issue_access_token(user: OrganizationUser, expires_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "group_id": user.group_id,
            "purpose": "organization_access",
            "iat": now,
            "exp": expires_at,
            "jti": secrets.token_urlsafe(24),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _create_session(db: Session, user: OrganizationUser, device_label: Optional[str] = None) -> dict:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES)
    refresh_expires_at = now + timedelta(days=30)
    access_token = _issue_access_token(user, expires_at)
    refresh_token = secrets.token_urlsafe(48)
    db.add(
        OrganizationSession(
            organization_user_id=user.id,
            token_hash=_token_digest(access_token),
            refresh_token_hash=_token_digest(refresh_token),
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            device_label=(device_label or "Unknown device")[:120],
            last_used_at=now,
        )
    )
    db.add(
        ControlPlaneAuditLog(
            action="ORGANIZATION_LOGIN",
            target_slug="CONTROL_PLANE",
            actor=user.email,
            details=f"Organization user {user.id} authenticated for group {user.group_id}.",
        )
    )
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES * 60,
        "refresh_expires_in": 30 * 24 * 60 * 60,
        "user": _user_payload(user),
    }


def _user_payload(user: OrganizationUser) -> dict:
    return {
        "id": user.id,
        "group_id": user.group_id,
        "email": user.email,
        "full_name": user.full_name,
        "group_role": user.group_role,
        "mfa_enabled": user.mfa_enabled,
    }


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _authenticate_token(token: str) -> Optional[dict]:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    subject, group_id = claims.get("sub"), claims.get("group_id")
    if (
        claims.get("purpose") != "organization_access"
        or not isinstance(subject, str)
        or not subject.isdecimal()
        or not isinstance(group_id, int)
    ):
        return None
    with ControlSessionLocal() as db:
        session = db.execute(
            select(OrganizationSession).where(
                OrganizationSession.token_hash == _token_digest(token),
                OrganizationSession.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if not session or session.organization_user_id != int(subject):
            return None
        expiry = session.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            return None
        user = db.get(OrganizationUser, session.organization_user_id)
        group = db.get(HospitalGroup, group_id)
        if (
            not user
            or user.group_id != group_id
            or user.status != "ACTIVE"
            or not group
            or group.status != "ACTIVE"
        ):
            return None
        return {"user_id": user.id, "group_id": user.group_id, "token_hash": session.token_hash, "session_id": session.id}


def _current_identity(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Organization bearer token required.")
    identity = _authenticate_token(authorization[7:].strip())
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid or expired organization session.")
    return identity


@router.post(
    "/login",
    dependencies=[Depends(_LOGIN_LIMIT)],
)
def login(payload: OrganizationLogin, db: Session = Depends(get_control_db), user_agent: Optional[str] = Header(default=None, alias="User-Agent")):
    group = db.execute(
        select(HospitalGroup).where(HospitalGroup.code == payload.group_code)
    ).scalar_one_or_none()
    user = None
    if group:
        user = db.execute(
            select(OrganizationUser)
            .where(
                OrganizationUser.group_id == group.id,
                OrganizationUser.email_normalized == payload.email.lower(),
            )
            .with_for_update()
        ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not user or not group or group.status != "ACTIVE" or user.status != "ACTIVE":
        pwd_context.verify(payload.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid credentials or unavailable account.")

    locked_until = user.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > now:
        pwd_context.verify(payload.password, user.password_hash or _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid credentials or unavailable account.")

    if not user.password_hash or not pwd_context.verify(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.failed_login_attempts = 0
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials or unavailable account.")

    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="Email verification is required.")
    user.failed_login_attempts = 0
    user.locked_until = None

    if user.group_role == "OWNER" and not user.mfa_enabled:
        db.commit()
        return {
            "mfa_setup_required": True,
            "mfa_token": _challenge_token(user, "organization_mfa_setup"),
        }
    if user.mfa_enabled:
        db.commit()
        return {
            "mfa_required": True,
            "mfa_token": _challenge_token(user, "organization_mfa_login"),
        }
    return _create_session(db, user, user_agent)


@router.post("/mfa/setup", dependencies=[Depends(_MFA_LIMIT)])
def setup_mfa(payload: MfaChallenge, db: Session = Depends(get_control_db)):
    user = _load_challenge(db, payload.mfa_token, "organization_mfa_setup")
    if user.group_role != "OWNER":
        raise HTTPException(status_code=403, detail="Only the Group Owner can use mandatory owner MFA setup.")
    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled.")
    if user.mfa_secret_encrypted:
        secret = decrypt_tenant_secret(user.mfa_secret_encrypted)
    else:
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
        user.mfa_secret_encrypted = encrypt_tenant_secret(secret)
        db.commit()
    return {
        "secret": secret,
        "otpauth_uri": (
            f"otpauth://totp/Avinya%20HMS:{user.email}"
            f"?secret={secret}&issuer=Avinya%20HMS&digits=6&period=30"
        ),
    }


@router.post("/mfa/confirm", dependencies=[Depends(_MFA_LIMIT)])
def confirm_mfa(payload: MfaVerification, db: Session = Depends(get_control_db), user_agent: Optional[str] = Header(default=None, alias="User-Agent")):
    user = _load_challenge(db, payload.mfa_token, "organization_mfa_setup")
    if user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="MFA setup has not been started.")
    counter = matching_totp_counter(decrypt_tenant_secret(user.mfa_secret_encrypted), payload.code)
    if counter is None:
        raise HTTPException(status_code=400, detail="Invalid MFA code.")
    user.mfa_enabled = True
    user.mfa_last_used_counter = counter
    return _create_session(db, user, user_agent)


@router.post("/mfa/verify-login", dependencies=[Depends(_MFA_LIMIT)])
def verify_mfa_login(payload: MfaVerification, db: Session = Depends(get_control_db), user_agent: Optional[str] = Header(default=None, alias="User-Agent")):
    user = _load_challenge(db, payload.mfa_token, "organization_mfa_login")
    if not user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=401, detail="MFA is not configured.")
    counter = matching_totp_counter(decrypt_tenant_secret(user.mfa_secret_encrypted), payload.code)
    if counter is None or (
        user.mfa_last_used_counter is not None
        and counter <= user.mfa_last_used_counter
    ):
        raise HTTPException(status_code=401, detail="Invalid MFA challenge or code.")
    user.mfa_last_used_counter = counter
    return _create_session(db, user, user_agent)


@router.post("/refresh", dependencies=[Depends(_LOGIN_LIMIT)])
def refresh_session(payload: RefreshRequest, db: Session = Depends(get_control_db)):
    now = datetime.now(timezone.utc)
    session = db.execute(
        select(OrganizationSession)
        .where(
            OrganizationSession.refresh_token_hash == _token_digest(payload.refresh_token),
            OrganizationSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not session or not session.refresh_expires_at:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    expiry = session.refresh_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    user = db.get(OrganizationUser, session.organization_user_id)
    group = db.get(HospitalGroup, user.group_id) if user else None
    if not user or user.status != "ACTIVE" or not group or group.status != "ACTIVE":
        session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Organization account is unavailable.")

    access_expiry = now + timedelta(minutes=settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES)
    access_token = _issue_access_token(user, access_expiry)
    refresh_token = secrets.token_urlsafe(48)
    session.token_hash = _token_digest(access_token)
    session.refresh_token_hash = _token_digest(refresh_token)
    session.expires_at = access_expiry
    session.refresh_expires_at = now + timedelta(days=30)
    session.last_used_at = now
    db.add(ControlPlaneAuditLog(
        action="ORGANIZATION_SESSION_REFRESH",
        target_slug="CONTROL_PLANE",
        actor=user.email,
        details=f"Rotated organization session {session.id}.",
    ))
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES * 60,
        "refresh_expires_in": 30 * 24 * 60 * 60,
        "user": _user_payload(user),
    }


@router.get("/branches")
def list_my_branch_access(
    identity: dict = Depends(_current_identity),
    db: Session = Depends(get_control_db),
):
    """List only active, verified branch assignments belonging to this organization identity."""
    rows = db.execute(
        select(BranchMembership, Branch, TenantRegistry)
        .join(Branch, Branch.id == BranchMembership.branch_id)
        .join(TenantRegistry, TenantRegistry.id == Branch.tenant_registry_id)
        .join(OrganizationUser, OrganizationUser.id == BranchMembership.organization_user_id)
        .join(HospitalGroup, HospitalGroup.id == BranchMembership.group_id)
        .join(BranchUserLink, BranchUserLink.membership_id == BranchMembership.id)
        .where(
            BranchMembership.organization_user_id == identity["user_id"],
            BranchMembership.group_id == identity["group_id"],
            BranchMembership.status == "ACTIVE",
            Branch.status == "ACTIVE",
            TenantRegistry.is_active.is_(True),
            OrganizationUser.status == "ACTIVE",
            HospitalGroup.id == identity["group_id"],
            HospitalGroup.status == "ACTIVE",
            BranchUserLink.verified_at.is_not(None),
        )
        .order_by(Branch.name.asc(), Branch.id.asc())
    ).all()
    return {
        "items": [
            {
                "membership_id": membership.id,
                "branch_id": branch.id,
                "branch_code": branch.code,
                "branch_name": branch.name,
                "subdomain_slug": registry.subdomain_slug,
            }
            for membership, branch, registry in rows
        ],
        "count": len(rows),
    }


@router.post("/branches/{branch_id}/access")
def create_branch_access_grant(
    branch_id: int,
    identity: dict = Depends(_current_identity),
    db: Session = Depends(get_control_db),
):
    """Issue a short-lived opaque handoff credential for one verified branch membership."""
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(BranchMembership, Branch, TenantRegistry, BranchUserLink)
        .join(Branch, Branch.id == BranchMembership.branch_id)
        .join(TenantRegistry, TenantRegistry.id == Branch.tenant_registry_id)
        .join(BranchUserLink, BranchUserLink.membership_id == BranchMembership.id)
        .join(OrganizationUser, OrganizationUser.id == BranchMembership.organization_user_id)
        .join(HospitalGroup, HospitalGroup.id == BranchMembership.group_id)
        .where(
            BranchMembership.organization_user_id == identity["user_id"],
            BranchMembership.group_id == identity["group_id"],
            BranchMembership.branch_id == branch_id,
            BranchMembership.status == "ACTIVE",
            Branch.status == "ACTIVE",
            TenantRegistry.is_active.is_(True),
            OrganizationUser.status == "ACTIVE",
            HospitalGroup.status == "ACTIVE",
            BranchUserLink.verified_at.is_not(None),
        )
        .with_for_update()
    ).first()
    if not row:
        raise HTTPException(status_code=403, detail="No active, verified membership grants access to this branch.")

    membership, branch, registry, link = row
    session = db.execute(
        select(OrganizationSession).where(
            OrganizationSession.id == identity["session_id"],
            OrganizationSession.organization_user_id == identity["user_id"],
            OrganizationSession.revoked_at.is_(None),
            OrganizationSession.expires_at > now,
        ).with_for_update()
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Organization session is no longer active.")

    raw_token = "br_access_" + secrets.token_urlsafe(48)
    expires_at = now + timedelta(minutes=10)
    grant = BranchAccessSession(
        organization_session_id=session.id,
        membership_id=membership.id,
        token_hash=_token_digest(raw_token),
        expires_at=expires_at,
    )
    db.add(grant)
    db.flush()
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
    db.add(ControlPlaneAuditLog(
        action="ORGANIZATION_BRANCH_ACCESS_GRANT_ISSUED",
        target_slug=registry.subdomain_slug,
        actor=str(identity["user_id"]),
        details=f"Short-lived branch access grant issued for membership {membership.id}; grant_id={grant.id}.",
    ))
    db.commit()
    return {
        "branch_access_token": raw_token,
        "token_type": "bearer",
        "expires_in": 600,
        "expires_at": expires_at,
        "grant_id": grant.id,
        "branch": {
            "id": branch.id,
            "code": branch.code,
            "name": branch.name,
            "subdomain_slug": registry.subdomain_slug,
            "api_base_url": registry.api_base_url,
        },
        "local_user_id": link.local_user_id,
        "roles": roles,
        "departments": departments,
        "message": "Short-lived branch handoff issued. Branch-side validation is a separate integration step; this credential alone does not bypass branch authentication.",
    }


@router.delete("/branch-access/{grant_id}")
def revoke_branch_access_grant(
    grant_id: int,
    identity: dict = Depends(_current_identity),
    db: Session = Depends(get_control_db),
):
    grant = db.execute(
        select(BranchAccessSession)
        .join(OrganizationSession, OrganizationSession.id == BranchAccessSession.organization_session_id)
        .where(
            BranchAccessSession.id == grant_id,
            OrganizationSession.organization_user_id == identity["user_id"],
            BranchAccessSession.revoked_at.is_(None),
        ).with_for_update()
    ).scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=404, detail="Active branch access grant not found.")
    grant.revoked_at = datetime.now(timezone.utc)
    db.add(ControlPlaneAuditLog(
        action="ORGANIZATION_BRANCH_ACCESS_GRANT_REVOKED",
        target_slug="CONTROL_PLANE",
        actor=str(identity["user_id"]),
        details=f"Branch access grant {grant.id} revoked by its owner.",
    ))
    db.commit()
    return {"status": "success", "revoked_grant_id": grant_id}


def require_organization_roles(*roles: str):
    allowed = frozenset(role.upper() for role in roles)

    def dependency(
        identity: dict = Depends(_current_identity),
        db: Session = Depends(get_control_db),
    ) -> dict:
        if not allowed:
            return identity
        user = db.get(OrganizationUser, identity["user_id"])
        if (
            not user
            or user.group_id != identity["group_id"]
            or user.group_role.upper() not in allowed
        ):
            raise HTTPException(status_code=403, detail="Insufficient organization permissions.")
        return identity

    return dependency


@router.get("/sessions")
def list_sessions(identity: dict = Depends(_current_identity), db: Session = Depends(get_control_db)):
    now = datetime.now(timezone.utc)
    sessions = db.execute(
        select(OrganizationSession)
        .where(
            OrganizationSession.organization_user_id == identity["user_id"],
            OrganizationSession.revoked_at.is_(None),
            OrganizationSession.refresh_expires_at > now,
        )
        .order_by(OrganizationSession.created_at.desc())
    ).scalars().all()
    return {
        "sessions": [
            {
                "id": item.id,
                "device_label": item.device_label or "Unknown device",
                "created_at": item.created_at,
                "last_used_at": item.last_used_at,
                "expires_at": item.refresh_expires_at,
                "current": item.id == identity["session_id"],
            }
            for item in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: int, identity: dict = Depends(_current_identity), db: Session = Depends(get_control_db)):
    session = db.execute(
        select(OrganizationSession)
        .where(
            OrganizationSession.id == session_id,
            OrganizationSession.organization_user_id == identity["user_id"],
            OrganizationSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found.")
    session.revoked_at = datetime.now(timezone.utc)
    db.add(ControlPlaneAuditLog(
        action="ORGANIZATION_SESSION_REVOKED",
        target_slug="CONTROL_PLANE",
        actor=str(identity["user_id"]),
        details=f"Organization session {session.id} revoked by its owner.",
    ))
    db.commit()
    return {"status": "success", "revoked_session_id": session_id}


@router.post("/logout-all")
def logout_all(identity: dict = Depends(_current_identity), db: Session = Depends(get_control_db)):
    now = datetime.now(timezone.utc)
    db.query(OrganizationSession).filter(
        OrganizationSession.organization_user_id == identity["user_id"],
        OrganizationSession.revoked_at.is_(None),
    ).update({OrganizationSession.revoked_at: now}, synchronize_session=False)
    db.add(ControlPlaneAuditLog(
        action="ORGANIZATION_LOGOUT_ALL",
        target_slug="CONTROL_PLANE",
        actor=str(identity["user_id"]),
        details="All organization sessions revoked by authenticated user.",
    ))
    db.commit()
    return {"status": "success", "message": "All organization sessions have been revoked."}


@router.get("/me")
def me(identity: dict = Depends(_current_identity), db: Session = Depends(get_control_db)):
    user = db.get(OrganizationUser, identity["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="Organization account is unavailable.")
    return {"user": _user_payload(user)}


@router.post("/logout")
def logout(identity: dict = Depends(_current_identity), db: Session = Depends(get_control_db)):
    session = db.execute(
        select(OrganizationSession).where(
            OrganizationSession.token_hash == identity["token_hash"],
            OrganizationSession.revoked_at.is_(None),
        ).with_for_update()
    ).scalar_one_or_none()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(
            ControlPlaneAuditLog(
                action="ORGANIZATION_LOGOUT",
                target_slug="CONTROL_PLANE",
                actor=str(identity["user_id"]),
                details="Organization session revoked by its authenticated user.",
            )
        )
        db.commit()
    return {"status": "success", "message": "This organization session has been revoked."}
