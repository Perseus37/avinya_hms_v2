from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.control_plane.models import (
    Branch,
    ControlPlaneAuditLog,
    HospitalGroup,
    TenantRegistry,
)
from backend.control_plane.services.auth import require_operator_role
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
        "database_name": tenant.db_name,
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
