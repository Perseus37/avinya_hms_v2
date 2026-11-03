"""create OPD queue orchestration tables

Revision ID: a1b2c3d4e5f6
Revises: f9b7c3d1e205
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f9b7c3d1e205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    queue_status = sa.Enum("OPEN", "PAUSED", "CLOSED", name="opd_queue_status")
    entry_status = sa.Enum(
        "WAITING", "CALLED", "ARRIVED", "IN_CONSULTATION",
        "ON_HOLD", "TRANSFERRED", "NO_SHOW", "COMPLETED",
        name="opd_queue_entry_status",
    )
    bind = op.get_bind()
    queue_status.create(bind, checkfirst=True)
    entry_status.create(bind, checkfirst=True)

    op.create_table(
        "opd_queues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("branch_code", sa.String(64), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("room_label", sa.String(100)),
        sa.Column("status", queue_status, nullable=False, server_default="OPEN"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer()),
        sa.Column("updated_by_id", sa.Integer()),
        sa.UniqueConstraint(
            "branch_code", "service_date", "department_id", "doctor_id",
            name="uq_opd_queue_branch_date_department_doctor",
        ),
    )
    op.create_index("ix_opd_queues_branch_date", "opd_queues", ["branch_code", "service_date"])

    op.create_table(
        "opd_queue_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Integer(), sa.ForeignKey("opd_queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("patient_encounters.id", ondelete="SET NULL")),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("state", entry_status, nullable=False, server_default="WAITING"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("first_called_at", sa.DateTime(timezone=True)),
        sa.Column("last_called_at", sa.DateTime(timezone=True)),
        sa.Column("arrived_at", sa.DateTime(timezone=True)),
        sa.Column("consultation_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("reason_code", sa.String(40)),
        sa.Column("reason_note", sa.String(500)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer()),
        sa.Column("updated_by_id", sa.Integer()),
        sa.UniqueConstraint("appointment_id", name="uq_opd_queue_entry_appointment"),
        sa.UniqueConstraint("queue_id", "queue_position", name="uq_opd_queue_entry_position"),
    )
    op.create_index(
        "ix_opd_queue_entries_queue_state_position",
        "opd_queue_entries", ["queue_id", "state", "queue_position"],
    )

    op.create_table(
        "opd_queue_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Integer(), sa.ForeignKey("opd_queues.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("opd_queue_entries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_state", sa.String(32)),
        sa.Column("to_state", sa.String(32)),
        sa.Column("reason_code", sa.String(40)),
        sa.Column("reason_note", sa.String(500)),
        sa.Column("event_metadata", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_opd_queue_events_queue_created", "opd_queue_events", ["queue_id", "created_at"])
    op.create_index("ix_opd_queue_events_entry_created", "opd_queue_events", ["entry_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_opd_queue_events_entry_created", table_name="opd_queue_events")
    op.drop_index("ix_opd_queue_events_queue_created", table_name="opd_queue_events")
    op.drop_table("opd_queue_events")
    op.drop_index("ix_opd_queue_entries_queue_state_position", table_name="opd_queue_entries")
    op.drop_table("opd_queue_entries")
    op.drop_index("ix_opd_queues_branch_date", table_name="opd_queues")
    op.drop_table("opd_queues")
    bind = op.get_bind()
    sa.Enum(name="opd_queue_entry_status").drop(bind, checkfirst=True)
    sa.Enum(name="opd_queue_status").drop(bind, checkfirst=True)
