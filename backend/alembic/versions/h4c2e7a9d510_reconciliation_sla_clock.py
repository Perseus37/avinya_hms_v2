"""Add pause-aware SLA clocks and breach timestamps to reconciliation cases."""
from alembic import op
import sqlalchemy as sa

revision = "h4c2e7a9d510"
down_revision = "h3b7d9e2a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("sla_paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("sla_paused_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_proc_recon_exception_sla_paused_seconds_nonneg",
        "procurement_reconciliation_exceptions",
        "sla_paused_seconds >= 0",
    )
    op.create_index(
        "ix_proc_recon_exception_sla_pause",
        "procurement_reconciliation_exceptions",
        ["status", "sla_paused_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_proc_recon_exception_sla_pause",
        table_name="procurement_reconciliation_exceptions",
    )
    op.drop_constraint(
        "ck_proc_recon_exception_sla_paused_seconds_nonneg",
        "procurement_reconciliation_exceptions",
        type_="check",
    )
    op.drop_column("procurement_reconciliation_exceptions", "sla_breached_at")
    op.drop_column("procurement_reconciliation_exceptions", "sla_paused_seconds")
    op.drop_column("procurement_reconciliation_exceptions", "sla_paused_at")
