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
    ControlPlaneAuditLog,
    HospitalGroup,
    OrganizationSession,
    OrganizationUser,
)
from backend.core.config import settings
from backend.core.database import ControlSessionLocal, get_control_db
from backend.core.dependencies import RateLimiter
from backend.domains.identity.passwords import pwd_context
from backend.security.envelope import decrypt_tenant_secret, encrypt_tenant_secret
from backend.security.totp import matching_totp_counter

router = APIRouter(prefix="/api/organization-auth", tags=["Hospital Organization Identity"])
_LOGIN_LIMIT = RateLimiter(scope="organization_auth_login", max_requests=10, window_seconds=60)
_MFA_LIMIT = RateLimiter(scope="organization_auth_mfa", max_requests=5, window_seconds=300)
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


def _create_session(db: Session, user: OrganizationUser) -> dict:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES)
    token = jwt.encode(
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
    db.add(
        OrganizationSession(
            organization_user_id=user.id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
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
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.CONTROL_PLANE_ACCESS_TOKEN_MINUTES * 60,
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
        return {"user_id": user.id, "group_id": user.group_id, "token_hash": session.token_hash}


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
def login(payload: OrganizationLogin, db: Session = Depends(get_control_db)):
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
    return _create_session(db, user)


@router.post("/mfa/setup")
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
def confirm_mfa(payload: MfaVerification, db: Session = Depends(get_control_db)):
    user = _load_challenge(db, payload.mfa_token, "organization_mfa_setup")
    if user.mfa_enabled or not user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="MFA setup has not been started.")
    counter = matching_totp_counter(decrypt_tenant_secret(user.mfa_secret_encrypted), payload.code)
    if counter is None:
        raise HTTPException(status_code=400, detail="Invalid MFA code.")
    user.mfa_enabled = True
    user.mfa_last_used_counter = counter
    return _create_session(db, user)


@router.post("/mfa/verify-login", dependencies=[Depends(_MFA_LIMIT)])
def verify_mfa_login(payload: MfaVerification, db: Session = Depends(get_control_db)):
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
    return _create_session(db, user)


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
