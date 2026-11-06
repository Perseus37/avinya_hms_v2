"""Add structured reconciliation resolution evidence and reopen tracking."""
from alembic import op
import sqlalchemy as sa

revision = "f4c8a2d7e610"
down_revision = "e4b8c2d7a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("root_cause_code", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("resolution_checklist", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("reopen_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_proc_recon_exception_reopen_count_nonneg",
        "procurement_reconciliation_exceptions",
        "reopen_count >= 0",
    )
    op.add_column("procurement_reconciliation_exceptions", sa.Column("resolution_review_status", sa.String(16), server_default="NOT_REQUIRED", nullable=False))
    op.add_column("procurement_reconciliation_exceptions", sa.Column("resolution_submitted_by_id", sa.Integer(), nullable=True))
    op.add_column("procurement_reconciliation_exceptions", sa.Column("resolution_reviewed_by_id", sa.Integer(), nullable=True))
    op.add_column("procurement_reconciliation_exceptions", sa.Column("resolution_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_proc_recon_resolution_review_status", "procurement_reconciliation_exceptions", "resolution_review_status IN ('NOT_REQUIRED','PENDING','APPROVED','REJECTED')")


def downgrade() -> None:
    op.drop_constraint(
        "ck_proc_recon_exception_reopen_count_nonneg",
        "procurement_reconciliation_exceptions",
        type_="check",
    )
    op.drop_column("procurement_reconciliation_exceptions", "reopen_count")
    op.drop_column("procurement_reconciliation_exceptions", "resolution_checklist")
    op.drop_column("procurement_reconciliation_exceptions", "root_cause_code")
