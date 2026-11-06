"""Persist procurement reconciliation exceptions and investigation events."""
from alembic import op
import sqlalchemy as sa

revision = "d7a4c2e9f610"
down_revision = "c6e2a9d4f710"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.String(255), nullable=False),
        sa.Column("exception_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), server_default="OPEN", nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_amount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unmatched_amount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detection_snapshot", sa.JSON(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("fingerprint", name="uq_proc_recon_exception_fingerprint"),
        sa.CheckConstraint("status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')", name="ck_proc_recon_exception_status"),
        sa.CheckConstraint("severity IN ('CRITICAL','HIGH','MEDIUM','LOW')", name="ck_proc_recon_exception_severity"),
    )
    op.create_index("ix_proc_recon_exception_queue", "procurement_reconciliation_exceptions", ["status", "severity", "last_detected_at"])
    op.create_index("ix_proc_recon_exception_assignee", "procurement_reconciliation_exceptions", ["assigned_to_id", "status"])
    op.create_index("ix_proc_recon_exception_reference", "procurement_reconciliation_exceptions", ["reference_type", "reference_id"])
    op.create_table(
        "procurement_reconciliation_exception_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("exception_id", sa.Integer(), sa.ForeignKey("procurement_reconciliation_exceptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("old_status", sa.String(16), nullable=True),
        sa.Column("new_status", sa.String(16), nullable=True),
        sa.Column("old_assignee_id", sa.Integer(), nullable=True),
        sa.Column("new_assignee_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_proc_recon_exception_event_time", "procurement_reconciliation_exception_events", ["exception_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_proc_recon_exception_event_time", table_name="procurement_reconciliation_exception_events")
    op.drop_table("procurement_reconciliation_exception_events")
    op.drop_index("ix_proc_recon_exception_reference", table_name="procurement_reconciliation_exceptions")
    op.drop_index("ix_proc_recon_exception_assignee", table_name="procurement_reconciliation_exceptions")
    op.drop_index("ix_proc_recon_exception_queue", table_name="procurement_reconciliation_exceptions")
    op.drop_table("procurement_reconciliation_exceptions")
