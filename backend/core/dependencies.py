import hashlib
import ipaddress
import json
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer, OAuth2PasswordBearer
import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from backend.core.config import settings
from backend.control_plane.models import (
    Branch, BranchAccessSession, BranchDepartmentAssignment, BranchMembership,
    BranchMembershipRole, BranchUserLink, FederatedNode, HospitalGroup,
    OrganizationSession, OrganizationUser, TenantRegistry,
)
from backend.core.database import (
    ControlSessionLocal, TenantContext, get_control_db, get_db, get_redis,
    resolve_tenant_context,
)
from backend.domains.facility.models import Bed
from backend.domains.identity.models import (
    AuthSession, Department, Permission, Role, User, UserRole, UserStatusEnum,
)

http_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="HTTPBearer",
    description="Paste your JWT Bearer token obtained from /api/auth/login or /api/auth/token (without 'Bearer ' prefix)",
)
tenant_header_scheme = APIKeyHeader(
    name="X-Hospital-Subdomain",
    auto_error=False,
    scheme_name="TenantSubdomain",
    description="Tenant subdomain slug (e.g. 'default' or your newly created hospital slug)",
)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token",
    auto_error=False,
    scheme_name="OAuth2PasswordBearer",
    description="OAuth2 password flow. Username = email, Password = password, Client ID = optional hospital slug.",
)


def validate_pagination(page: int = 1, page_size: int = 20) -> tuple[int, int]:
    """Enforces safe pagination boundaries across all list endpoints."""
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")
    if page_size < 1 or page_size > settings.MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Page size must be between 1 and {settings.MAX_PAGE_SIZE}",
        )
    return page, page_size


def _authenticate_branch_access_token(
    raw_token: str,
    tenant: TenantContext,
    local_db: Session,
) -> User:
    """Resolve a central short-lived grant against this request's trusted branch context."""
    if not raw_token.startswith("br_access_") or len(raw_token) < 50:
        raise HTTPException(status_code=401, detail="Invalid branch access credential.")

    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    try:
        with ControlSessionLocal() as control_db:
            row = control_db.execute(
                select(
                    BranchAccessSession,
                    BranchMembership,
                    Branch,
                    TenantRegistry,
                    BranchUserLink,
                    OrganizationSession,
                    OrganizationUser,
                    HospitalGroup,
                )
                .join(BranchMembership, BranchMembership.id == BranchAccessSession.membership_id)
                .join(Branch, Branch.id == BranchMembership.branch_id)
                .join(TenantRegistry, TenantRegistry.id == Branch.tenant_registry_id)
                .join(BranchUserLink, BranchUserLink.membership_id == BranchMembership.id)
                .join(OrganizationSession, OrganizationSession.id == BranchAccessSession.organization_session_id)
                .join(OrganizationUser, OrganizationUser.id == BranchMembership.organization_user_id)
                .join(HospitalGroup, HospitalGroup.id == BranchMembership.group_id)
                .where(
                    BranchAccessSession.token_hash == digest,
                    BranchAccessSession.revoked_at.is_(None),
                    BranchAccessSession.expires_at > now,
                    BranchMembership.status == "ACTIVE",
                    Branch.status == "ACTIVE",
                    TenantRegistry.is_active.is_(True),
                    TenantRegistry.subdomain_slug == tenant.subdomain_slug,
                    TenantRegistry.branch_code == tenant.branch_code,
                    OrganizationSession.revoked_at.is_(None),
                    OrganizationSession.expires_at > now,
                    OrganizationUser.status == "ACTIVE",
                    HospitalGroup.status == "ACTIVE",
                    BranchUserLink.verified_at.is_not(None),
                )
            ).one_or_none()
            if not row:
                raise HTTPException(status_code=401, detail="Branch access grant is invalid, expired, revoked, or not valid for this branch.")

            grant, membership, branch, registry, link, org_session, org_user, group = row
            if (
                branch.group_id != group.id
                or membership.group_id != group.id
                or membership.organization_user_id != org_user.id
                or org_session.organization_user_id != org_user.id
            ):
                raise HTTPException(status_code=401, detail="Branch access grant identity binding is invalid.")

            local_user = local_db.get(User, link.local_user_id)
            if (
                not local_user
                or local_user.status != UserStatusEnum.ACTIVE
                or local_user.is_superuser
                or local_user.email.strip().lower() != org_user.email_normalized
                or " ".join(local_user.full_name.split()).casefold()
                != " ".join(org_user.full_name.split()).casefold()
            ):
                raise HTTPException(
                    status_code=401,
                    detail="Linked branch user is unavailable or no longer matches the verified organization identity.",
                )

            assigned_roles = control_db.execute(
                select(BranchMembershipRole.role_code)
                .where(BranchMembershipRole.membership_id == membership.id)
            ).scalars().all()
            assigned_departments = control_db.execute(
                select(BranchDepartmentAssignment.department_code)
                .where(BranchDepartmentAssignment.membership_id == membership.id)
            ).scalars().all()

            local_role_codes = set(
                local_db.execute(
                    select(Role.code).where(Role.code.in_(assigned_roles))
                ).scalars().all()
            ) if assigned_roles else set()
            if local_role_codes != set(assigned_roles):
                raise HTTPException(status_code=403, detail="A centrally assigned role no longer exists in this branch.")

            # Central membership narrows existing local permissions; it never creates or
            # elevates local role assignments. Superuser bypass is disabled for this mode.
            effective_roles = local_db.execute(
                select(Role)
                .join(Role.users)
                .where(User.id == local_user.id, Role.code.in_(assigned_roles))
                .order_by(Role.code.asc())
            ).scalars().all() if assigned_roles else []
            # Restrict both permission queries and direct role inspections performed by
            # legacy endpoints to the intersection of local roles and central assignments.
            set_committed_value(local_user, "roles", effective_roles)
            local_db.info["central_branch_role_codes"] = frozenset(
                role.code for role in effective_roles
            )
            local_db.info["central_branch_department_codes"] = frozenset(assigned_departments)
            local_db.info["central_branch_membership_id"] = membership.id
            local_db.info["central_branch_grant_id"] = grant.id
            local_db.info["audit_user_id"] = local_user.id
            return local_user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Central branch authorization is temporarily unavailable.",
        ) from exc


def get_current_user(
    request: Request,
    token: Any = Depends(http_bearer),
    oauth2_token: Optional[str] = Depends(oauth2_scheme),
    _tenant_header: Optional[str] = Depends(tenant_header_scheme),
    branch_access_token: Optional[str] = Header(default=None, alias="X-Branch-Access-Token"),
    db: Session = Depends(get_db),
) -> User:
    """Validates either a tenant JWT or an explicitly supplied central branch grant."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials for this hospital instance.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Explicit branch-grant mode is opt-in and takes precedence. An invalid grant
    # must never fall back to a simultaneously supplied legacy JWT.
    if branch_access_token:
        tenant: TenantContext = resolve_tenant_context(request)
        return _authenticate_branch_access_token(branch_access_token.strip(), tenant, db)

    raw_token = None
    if token and hasattr(token, "credentials") and token.credentials:
        raw_token = token.credentials
    elif token and isinstance(token, str):
        raw_token = token
    elif oauth2_token:
        raw_token = oauth2_token
    else:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.strip().lower().startswith("bearer "):
            raw_token = auth_header.strip().split(" ", 1)[1].strip()

    if not raw_token:
        raise credentials_exception

    tenant: TenantContext = resolve_tenant_context(request)
    try:
        payload = jwt.decode(raw_token, tenant.jwt_secret_key, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        token_tenant: str = payload.get("tenant_slug")
        token_branch: str = payload.get("branch_code")
        token_id = payload.get("jti")
        if (
            not isinstance(user_id, str)
            or not user_id.isdecimal()
            or token_tenant != tenant.subdomain_slug
            or token_branch != tenant.branch_code
            or "purpose" in payload
            or not isinstance(token_id, str)
            or not token_id
        ):
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if not user or user.status != UserStatusEnum.ACTIVE:
        raise credentials_exception
    auth_session = db.get(AuthSession, token_id)
    if (
        not auth_session
        or auth_session.user_id != user.id
        or auth_session.revoked_at is not None
    ):
        raise credentials_exception
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise credentials_exception

    # Populate audit actor ID for the SQLAlchemy before_flush listener in models.py
    db.info["audit_user_id"] = user.id
    return user


def user_has_permission(db: Session, user: User, *permission_codes: str) -> bool:
    """Helper to check if an authenticated user holds at least one of the specified granular permissions."""
    central_role_codes = db.info.get("central_branch_role_codes")
    if user.is_superuser and central_role_codes is None:
        return True
    if central_role_codes is not None and not central_role_codes:
        return False
    required_set = set(permission_codes)
    stmt = (
        select(Permission.id)
        .join(Role.permissions)
        .join(Role.users)
        .where(User.id == user.id)
        .where(Permission.code.in_(required_set))
        .limit(1)
    )
    if central_role_codes is not None:
        stmt = stmt.where(Role.code.in_(central_role_codes))
    return db.execute(stmt).scalar_one_or_none() is not None


def user_has_department_access(
    db: Session, user: User, department_id: int
) -> bool:
    """Check local assignment and, for central sessions, central department scope."""
    local_assignment = db.execute(
        select(UserRole.user_id)
        .join(Department, Department.id == UserRole.department_id)
        .where(
            UserRole.user_id == user.id,
            Department.id == department_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if local_assignment is None:
        return False

    central_department_codes = db.info.get("central_branch_department_codes")
    if central_department_codes is None:
        return True

    department_code = db.execute(
        select(Department.code).where(Department.id == department_id)
    ).scalar_one_or_none()
    return bool(department_code and department_code in central_department_codes)


def get_user_assigned_department_ids(db: Session, actor: User) -> Optional[set[int]]:
    """Return locally assigned departments intersected with central grant scope.

    None means legacy branch authentication, where existing route behavior is retained.
    """
    central_codes = db.info.get("central_branch_department_codes")
    if central_codes is None:
        return None
    if not central_codes:
        return set()
    return set(
        db.execute(
            select(UserRole.department_id)
            .join(Department, Department.id == UserRole.department_id)
            .where(
                UserRole.user_id == actor.id,
                UserRole.department_id.is_not(None),
                Department.code.in_(central_codes),
            )
            .distinct()
        ).scalars().all()
    )


def ensure_department_id_access(db: Session, department_id: int, actor: User) -> None:
    """Require the local department assignment and central department grant, when present."""
    if db.info.get("central_branch_department_codes") is None:
        return
    if not user_has_department_access(db, actor, department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource is outside your assigned department scope.",
        )




def ensure_department_code_access(
    db: Session, department_codes: set[str] | tuple[str, ...], actor: User
) -> None:
    """Require a local and centrally granted assignment to one of the named departments."""
    if db.info.get("central_branch_department_codes") is None:
        return
    codes = set(department_codes)
    department_ids = db.execute(
        select(Department.id).where(Department.code.in_(codes), Department.is_active.is_(True))
    ).scalars().all()
    if not any(user_has_department_access(db, actor, department_id) for department_id in department_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: an active assignment to the required operational department is needed.",
        )


def ensure_pharmacy_prescription_access(db: Session, prescription_id: int, actor: User) -> None:
    """Allow pharmacy staff or the treating department to access a prescription."""
    from backend.domains.pharmacy.models import Prescription
    from backend.domains.encounters.models import PatientEncounter

    prescription = db.get(Prescription, prescription_id)
    if prescription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")
    if db.info.get("central_branch_department_codes") is None:
        return
    try:
        ensure_department_code_access(db, {"PHARMACY", "DEPT_PHARMACY"}, actor)
        return
    except HTTPException as exc:
        if exc.status_code != status.HTTP_403_FORBIDDEN:
            raise
    ensure_encounter_department_access(db, prescription.encounter_id, actor)


def ensure_prescription_encounter_access(db: Session, encounter_id: int, actor: User) -> None:
    """Prescription creation remains a clinical action scoped to its encounter department."""
    ensure_encounter_department_access(db, encounter_id, actor)

def ensure_diagnostic_order_access(db: Session, order_id: int, actor: User) -> None:
    """Require clinical access to the patient's encounter department for order-level data."""
    allowed_ids = get_user_assigned_department_ids(db, actor)
    if allowed_ids is None:
        return
    from backend.domains.diagnostics.models import DiagnosticOrder
    from backend.domains.encounters.models import PatientEncounter

    order_exists = db.execute(
        select(DiagnosticOrder.id).where(DiagnosticOrder.id == order_id)
    ).scalar_one_or_none()
    if order_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic order not found.")
    clinical_match = db.execute(
        select(PatientEncounter.id)
        .join(DiagnosticOrder, DiagnosticOrder.patient_id == PatientEncounter.patient_id)
        .where(
            DiagnosticOrder.id == order_id,
            PatientEncounter.department_id.in_(allowed_ids),
        )
        .limit(1)
    ).scalar_one_or_none()
    if clinical_match is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diagnostic order is outside your assigned clinical department scope.",
        )

def ensure_diagnostic_task_department_access(db: Session, task_id: int, actor: User) -> None:
    """Require assignment to the department that owns the diagnostic service."""
    allowed_ids = get_user_assigned_department_ids(db, actor)
    if allowed_ids is None:
        return
    from backend.domains.diagnostics.models import DiagnosticTask, ServiceCatalog, ServiceCategory
    department_id = db.execute(
        select(ServiceCategory.department_id)
        .join(ServiceCatalog, ServiceCatalog.category_id == ServiceCategory.id)
        .join(DiagnosticTask, DiagnosticTask.service_id == ServiceCatalog.id)
        .where(DiagnosticTask.id == task_id)
    ).scalar_one_or_none()
    if department_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic task not found.")
    if department_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Diagnostic task is outside your assigned service department.")

def ensure_queue_department_access(db: Session, queue_id: int, actor: User) -> None:
    from backend.domains.encounters.opd_queue_models import OPDQueue

    department_id = db.execute(
        select(OPDQueue.department_id).where(OPDQueue.id == queue_id)
    ).scalar_one_or_none()
    if department_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OPD queue not found.")
    ensure_department_id_access(db, department_id, actor)


def ensure_admission_department_access(db: Session, admission_id: int, actor: User) -> None:
    """Authorize an IPD admission through its parent encounter department."""
    allowed_ids = get_user_assigned_department_ids(db, actor)
    if allowed_ids is None:
        return
    from backend.domains.encounters.models import InpatientAdmission, PatientEncounter

    department_id = db.execute(
        select(PatientEncounter.department_id)
        .join(InpatientAdmission, InpatientAdmission.encounter_id == PatientEncounter.id)
        .where(InpatientAdmission.id == admission_id)
    ).scalar_one_or_none()
    if department_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admission not found.")
    if department_id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: admission is outside your assigned department scope.",
        )


def RequireAdmissionDepartmentAccess(admission_id_parameter: str = "admission_id"):
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        try:
            admission_id = int(request.path_params.get(admission_id_parameter))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid admission identifier is required.",
            )
        ensure_admission_department_access(db, admission_id, current_user)
        return current_user
    return dependency


def ensure_encounter_department_access(db: Session, encounter_id: int, actor: User) -> None:
    """Require both central membership and local department assignment for an encounter."""
    allowed_codes = db.info.get("central_branch_department_codes")
    if allowed_codes is None:
        return
    from backend.domains.encounters.models import PatientEncounter

    department = db.execute(
        select(Department)
        .join(PatientEncounter, PatientEncounter.department_id == Department.id)
        .where(PatientEncounter.id == encounter_id)
    ).scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found.")
    if department.code not in allowed_codes or not user_has_department_access(
        db, actor, department.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: encounter is outside your assigned department scope.",
        )


def ensure_patient_department_access(db: Session, patient_id: int, actor: User) -> None:
    """Allow patient-level access through an encounter in a centrally and locally assigned department."""
    allowed_codes = db.info.get("central_branch_department_codes")
    if allowed_codes is None:
        return
    from backend.domains.encounters.models import PatientEncounter

    department_ids = db.execute(
        select(PatientEncounter.department_id)
        .join(Department, PatientEncounter.department_id == Department.id)
        .where(
            PatientEncounter.patient_id == patient_id,
            Department.code.in_(allowed_codes),
        )
        .distinct()
    ).scalars().all()
    if not any(user_has_department_access(db, actor, department_id) for department_id in department_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient is not available within your assigned clinical scope.",
        )


def RequirePatientDepartmentAccess(patient_id_parameter: str = "patient_id"):
    """FastAPI dependency for patient visibility through an assigned clinical encounter."""
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        raw_patient_id = request.path_params.get(patient_id_parameter)
        try:
            patient_id = int(raw_patient_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid patient identifier is required.",
            )
        ensure_patient_department_access(db, patient_id, current_user)
        return current_user
    return dependency


def RequireEncounterDepartmentAccess(encounter_id_parameter: str = "encounter_id"):
    """Enforce encounter department scope for centrally granted branch sessions.

    Legacy branch JWT authorization is intentionally unchanged during migration.
    Encounter department is authoritative; patient-level department is not assumed.
    """
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        central_department_codes = db.info.get("central_branch_department_codes")
        if central_department_codes is None:
            return current_user

        raw_encounter_id = request.path_params.get(encounter_id_parameter)
        try:
            encounter_id = int(raw_encounter_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid encounter identifier is required.",
            )

        ensure_encounter_department_access(db, encounter_id, current_user)
        return current_user
    return dependency


def RequireDepartmentAccess(department_id_parameter: str = "department_id"):
    """FastAPI dependency enforcing branch-local and centrally assigned department scope."""
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        raw_department_id = request.path_params.get(department_id_parameter)
        if raw_department_id is None:
            raw_department_id = request.query_params.get(department_id_parameter)
        try:
            department_id = int(raw_department_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid department identifier is required.",
            )
        if not user_has_department_access(db, current_user, department_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: department is outside your assigned scope.",
            )
        return current_user
    return dependency


def RequirePermission(*permission_codes: str):
    """
    Strictly verifies that the authenticated user holds AT LEAST ONE of the exact
    `resource:action` permission codes required by the route. No legacy aliases.
    """
    if not permission_codes:
        raise ValueError("At least one permission code must be provided to RequirePermission.")

    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_has_permission(db, current_user, *permission_codes):
            formatted = "' or '".join(permission_codes)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Required permission '{formatted}' missing.",
            )
        return current_user

    return dependency


class RequireLicensedModule:
    """
    Enforces modular/bundle licensing per hospital tenant.
    Blocks requests with HTTP 403 if the hospital has not licensed the requested module.
    """

    def __init__(self, module_key: str):
        self.module_key = module_key

    def __call__(self, request: Request) -> None:
        tenant_ctx = resolve_tenant_context(request)
        try:
            enabled_modules = (
                json.loads(tenant_ctx.enabled_modules_json)
                if tenant_ctx.enabled_modules_json
                else {"all": True}
            )
        except (TypeError, json.JSONDecodeError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hospital module licensing configuration is invalid.",
            )
        if not isinstance(enabled_modules, dict):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Hospital module licensing configuration is invalid.",
            )

        if enabled_modules.get("all") is True:
            return

        if not enabled_modules.get(self.module_key, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{self.module_key}' is not enabled under your hospital's current license package.",
            )


def get_federated_node(
    x_federation_api_key: str = Header(..., alias="X-Federation-API-Key"),
    control_db: Session = Depends(get_control_db),
) -> FederatedNode:
    """Authenticates cross-branch/cross-tenant requests against the Control Plane."""
    if not x_federation_api_key or len(x_federation_api_key) < 16:
        raise HTTPException(status_code=401, detail="Invalid Federation API Key format.")

    key_hash = hashlib.sha256(x_federation_api_key.encode("utf-8")).hexdigest()
    stmt = select(FederatedNode).where(
        FederatedNode.api_key_hash == key_hash,
        FederatedNode.is_active == True,
    )
    node = control_db.execute(stmt).scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=401, detail="Unauthorized or revoked Federation API Key.")

    node.last_used_at = datetime.now(timezone.utc)
    control_db.commit()
    return node


def get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP address, safely resolving through trusted reverse proxies
    configured in settings.TRUSTED_PROXY_IPS. Prevents IP spoofing via forged headers (N-58).
    """
    client_ip = request.client.host if request.client else "unknown"
    if not getattr(settings, "TRUSTED_PROXY_IPS", "").strip():
        return client_ip

    try:
        trusted_proxies = [
            ipaddress.ip_network(cidr.strip(), strict=False)
            for cidr in settings.TRUSTED_PROXY_IPS.split(",")
            if cidr.strip()
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trusted proxy configuration is invalid.",
        ) from exc

    try:
        peer_ip = ipaddress.ip_address(client_ip)
    except ValueError:
        peer_ip = None

    if peer_ip and any(peer_ip in network for network in trusted_proxies):
        forwarded_ips = []
        for value in request.headers.get("X-Forwarded-For", "").split(","):
            try:
                forwarded_ips.append(ipaddress.ip_address(value.strip()))
            except ValueError:
                continue
        for candidate in reversed([*forwarded_ips, peer_ip]):
            if not any(candidate in network for network in trusted_proxies):
                client_ip = str(candidate)
                break

    return client_ip


class RateLimiter:
    """
    Fail-open Redis fixed-window rate limiter.
    Protects sensitive endpoints (login, federation discovery) without breaking
    the application if Redis is temporarily unreachable.
    """

    def __init__(self, scope: str, max_requests: int, window_seconds: int = 60):
        self.scope = scope
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def __call__(self, request: Request, redis_client=Depends(get_redis)) -> None:
        self._check(request, redis_client)

    def check_actor(
        self, request: Request, redis_client, actor: str, *, increment: bool = True
    ) -> None:
        self._check(request, redis_client, actor=actor, increment=increment)

    def get_key(self, request: Request, actor: str) -> str:
        tenant_slug = settings.DEFAULT_TENANT_SLUG
        try:
            from backend.core.database import extract_subdomain_slug
            tenant_slug = extract_subdomain_slug(request)
        except Exception:
            hostname = (request.url.hostname or "").lower().rstrip(".")
            base_domain = settings.BASE_DOMAIN.strip(".").lower()
            if hostname.endswith(f".{base_domain}"):
                candidate = hostname[: -(len(base_domain) + 1)]
                if candidate and "." not in candidate:
                    tenant_slug = candidate
        return f"rl:{self.scope}:{tenant_slug}:{actor}"

    def reset_actor(self, request: Request, redis_client, actor: str) -> None:
        if not redis_client:
            return
        key = self.get_key(request, actor)
        try:
            redis_client.delete(key)
        except Exception:
            pass

    def _check(
        self,
        request: Request,
        redis_client,
        actor: str | None = None,
        *,
        increment: bool = True,
    ) -> None:
        sensitive_auth_scope = self.scope.startswith(("auth_login", "auth_mfa"))
        if not redis_client:
            if sensitive_auth_scope:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication temporarily unavailable due to security infrastructure outage.",
                )
            return

        client_ip = get_client_ip(request)
        actor = actor or client_ip
        key = self.get_key(request, actor)

        try:
            current = redis_client.get(key)
            if current is not None and int(current) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({self.max_requests} requests per {self.window_seconds}s). Please retry shortly.",
                )
            if not increment:
                return
            # F-06: Atomic / pipelined rate limit increment with guaranteed TTL recovery.
            # If the process was previously interrupted between INCR and EXPIRE, or if the key
            # has lost its TTL (ttl == -1), the expiration window is immediately restored.
            if hasattr(redis_client, "pipeline"):
                pipe = redis_client.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                results = pipe.execute()
                count = results[0]
                key_ttl = results[1]
                if count == 1 or key_ttl == -1:
                    if hasattr(redis_client, "expire"):
                        redis_client.expire(key, self.window_seconds)
            elif hasattr(redis_client, "incr"):
                count = redis_client.incr(key)
                key_ttl = redis_client.ttl(key) if hasattr(redis_client, "ttl") else -1
                if count == 1 or key_ttl == -1:
                    if hasattr(redis_client, "expire"):
                        redis_client.expire(key, self.window_seconds)
            else:
                new_val = int(current or 0) + 1
                redis_client.set(key, str(new_val), ex=self.window_seconds)
        except HTTPException:
            raise
        except Exception:
            # SEC-001: Fail-closed for sensitive authentication paths to prevent brute force if Redis drops
            if sensitive_auth_scope:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication temporarily unavailable due to security infrastructure outage."
                )
            # Safe fail-open for generic/non-sensitive rate limits
            return


def enforce_tenant_resource_quota(
    request: Request,
    db: Session,
    resource: str,
    additional_count: int = 1,
) -> None:
    """
    Enforces commercial quota limits (max_beds, max_users) configured in TenantRegistry.quota_limits_json.
    Raises HTTP 403 Forbidden if provisioning additional_count resources would exceed the hospital's contract quota.
    """
    tenant = resolve_tenant_context(request)
    raw_quotas = tenant.quota_limits_json
    if not raw_quotas:
        return

    try:
        quotas = json.loads(raw_quotas) if isinstance(raw_quotas, str) else raw_quotas
    except Exception:
        return

    if resource == "beds":
        max_beds = quotas.get("max_beds")
        if max_beds is not None:
            current_beds = db.scalar(select(func.count(Bed.id))) or 0
            if current_beds + additional_count > int(max_beds):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Commercial Quota Exceeded: Hospital is licensed for a maximum of {max_beds} bed(s) "
                        f"(currently {current_beds} provisioned). Upgrade your bed quota in the Control Plane."
                    ),
                )

    elif resource == "users":
        max_users = quotas.get("max_users")
        if max_users is not None:
            current_users = db.scalar(select(func.count(User.id))) or 0
            if current_users + additional_count > int(max_users):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Commercial Quota Exceeded: Hospital is licensed for a maximum of {max_users} staff user(s) "
                        f"(currently {current_users} provisioned). Upgrade your user quota in the Control Plane."
                    ),
                )