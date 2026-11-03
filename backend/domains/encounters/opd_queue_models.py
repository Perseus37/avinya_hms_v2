"""OPD queue orchestration persistence.

Queue state is intentionally separate from Appointment and PatientEncounter state.
All tables live in the tenant database; branch_code is stamped from trusted tenant
context and never accepted from request payloads.
"""
from datetime import date, datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.audit import AuditMixin
from backend.core.database import Base


class OPDQueueStatus(str, PyEnum):
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class OPDQueueEntryStatus(str, PyEnum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    ARRIVED = "ARRIVED"
    IN_CONSULTATION = "IN_CONSULTATION"
    ON_HOLD = "ON_HOLD"
    TRANSFERRED = "TRANSFERRED"
    NO_SHOW = "NO_SHOW"
    COMPLETED = "COMPLETED"


class OPDQueue(AuditMixin, Base):
    __tablename__ = "opd_queues"
    __table_args__ = (
        UniqueConstraint(
            "branch_code", "service_date", "department_id", "doctor_id",
            name="uq_opd_queue_branch_date_department_doctor",
        ),
        Index("ix_opd_queues_branch_date", "branch_code", "service_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_code: Mapped[str] = mapped_column(String(64), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    room_label: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[OPDQueueStatus] = mapped_column(
        Enum(OPDQueueStatus, name="opd_queue_status"),
        nullable=False,
        default=OPDQueueStatus.OPEN,
        server_default=OPDQueueStatus.OPEN.value,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OPDQueueEntry(AuditMixin, Base):
    __tablename__ = "opd_queue_entries"
    __table_args__ = (
        UniqueConstraint("appointment_id", name="uq_opd_queue_entry_appointment"),
        UniqueConstraint("queue_id", "queue_position", name="uq_opd_queue_entry_position"),
        Index("ix_opd_queue_entries_queue_state_position", "queue_id", "state", "queue_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("opd_queues.id", ondelete="CASCADE"), nullable=False)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id", ondelete="RESTRICT"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    encounter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient_encounters.id", ondelete="SET NULL"))
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_position: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    state: Mapped[OPDQueueEntryStatus] = mapped_column(
        Enum(OPDQueueEntryStatus, name="opd_queue_entry_status"),
        nullable=False,
        default=OPDQueueEntryStatus.WAITING,
        server_default=OPDQueueEntryStatus.WAITING.value,
    )
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    first_called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    consultation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[Optional[str]] = mapped_column(String(40))
    reason_note: Mapped[Optional[str]] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OPDQueueEvent(Base):
    __tablename__ = "opd_queue_events"
    __table_args__ = (
        Index("ix_opd_queue_events_queue_created", "queue_id", "created_at"),
        Index("ix_opd_queue_events_entry_created", "entry_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("opd_queues.id", ondelete="RESTRICT"), nullable=False)
    entry_id: Mapped[int] = mapped_column(ForeignKey("opd_queue_entries.id", ondelete="RESTRICT"), nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(String(32))
    to_state: Mapped[Optional[str]] = mapped_column(String(32))
    reason_code: Mapped[Optional[str]] = mapped_column(String(40))
    reason_note: Mapped[Optional[str]] = mapped_column(String(500))
    event_metadata: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
