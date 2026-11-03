import hashlib
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import DateTime, ForeignKey, Integer, String, event, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.core.audit import AuditMixin
from backend.core.database import Base


class FederatedClient(AuditMixin, Base):
    """Authorized external branches allowed to request patient records."""

    __tablename__ = "federated_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    branch_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FederationTransferLog(Base):
    """Immutable audit log of cross-branch patient data lookups."""

    __tablename__ = "federation_transfer_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("federated_clients.id"), nullable=True, index=True
    )
    requesting_branch_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requested_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _sanitize_federation_identifier(identifier: str) -> str:
    """Prevent raw ABHA identifiers from entering the immutable audit trail.

    Discovery historically supplied values such as ``branch->abha:<ABHA>``.
    Preserve the caller/purpose context while replacing only the sensitive ABHA
    value with a deterministic fingerprint so repeated lookups remain correlatable.
    """
    marker = "abha:"
    if marker not in identifier.lower():
        return identifier

    prefix, value = identifier.split(marker, 1)
    if not value:
        return identifier
    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}abha_sha256:{fingerprint}"


@event.listens_for(Session, "before_flush")
def _protect_federation_transfer_logs(session: Session, flush_context, instances) -> None:
    """Enforce federation identity binding and protect immutable transfer logs."""
    expected_branch = session.info.get("tenant_branch_code")

    for entity in session.new:
        if isinstance(entity, FederatedClient):
            if expected_branch and entity.branch_code.strip().upper() != expected_branch.strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Federation identity must match the current tenant branch.",
                )

        if isinstance(entity, FederationTransferLog):
            entity.requested_identifier = _sanitize_federation_identifier(
                entity.requested_identifier
            )

    for entity in session.dirty:
        if isinstance(entity, FederationTransferLog) and session.is_modified(
            entity, include_collections=False
        ):
            raise ValueError("Federation transfer logs are immutable.")

    for entity in session.deleted:
        if isinstance(entity, FederationTransferLog):
            raise ValueError("Federation transfer logs are immutable and cannot be deleted.")