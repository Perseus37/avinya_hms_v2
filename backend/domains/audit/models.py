"""Append-only accountability metadata for generated security audit exports."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DDL, DateTime, ForeignKey, Index, Integer, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


class SecurityAuditExportRegister(Base):
    __tablename__ = "security_audit_export_register"
    __table_args__ = (
        CheckConstraint("schema_version >= 1", name="ck_security_audit_export_schema_version"),
        CheckConstraint("event_count >= 0", name="ck_security_audit_export_event_count"),
        CheckConstraint("byte_count >= 0", name="ck_security_audit_export_byte_count"),
        CheckConstraint("length(payload_sha256) = 64", name="ck_security_audit_export_sha256_length"),
        Index("ix_security_audit_export_exported_at", "exported_at"),
        Index("ix_security_audit_export_actor", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT", name="fk_security_audit_export_actor"), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    from_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    to_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


event.listen(
    SecurityAuditExportRegister.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS trg_security_audit_export_no_update "
        "BEFORE UPDATE ON security_audit_export_register "
        "BEGIN SELECT RAISE(ABORT, 'security audit export register is append-only'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    SecurityAuditExportRegister.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS trg_security_audit_export_no_delete "
        "BEFORE DELETE ON security_audit_export_register "
        "BEGIN SELECT RAISE(ABORT, 'security audit export register is append-only'); END"
    ).execute_if(dialect="sqlite"),
)
