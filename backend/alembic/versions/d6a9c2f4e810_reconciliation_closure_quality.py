"""Add reconciliation closure review and reopen tracking.

Revision ID: d6a9c2f4e810
Revises: b8d3f6a1c920
"""
from alembic import op
import sqlalchemy as sa

revision = "d6a9c2f4e810"
down_revision = "b8d3f6a1c920"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "procurement_reconciliation_investigations"
    op.add_column(table, sa.Column("closed_by_id", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(table, sa.Column("resolution_quality_status", sa.String(16), nullable=False, server_default="NOT_REVIEWED"))
    op.add_column(table, sa.Column("resolution_quality_reviewed_by_id", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("resolution_quality_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("resolution_quality_note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_recon_investigation_closed_by", table, "users", ["closed_by_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_recon_investigation_quality_reviewer", table, "users", ["resolution_quality_reviewed_by_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("ck_recon_investigation_reopen_count_nonneg", table, "reopen_count >= 0")
    op.create_check_constraint("ck_recon_investigation_quality_status", table, "resolution_quality_status IN ('NOT_REVIEWED','APPROVED','REJECTED')")
    op.create_index("ix_recon_investigation_closed_by", table, ["closed_by_id"])
    op.create_index("ix_recon_investigation_quality_reviewer", table, ["resolution_quality_reviewed_by_id"])


def downgrade() -> None:
    table = "procurement_reconciliation_investigations"
    op.drop_index("ix_recon_investigation_quality_reviewer", table_name=table)
    op.drop_index("ix_recon_investigation_closed_by", table_name=table)
    op.drop_constraint("ck_recon_investigation_quality_status", table, type_="check")
    op.drop_constraint("ck_recon_investigation_reopen_count_nonneg", table, type_="check")
    op.drop_constraint("fk_recon_investigation_quality_reviewer", table, type_="foreignkey")
    op.drop_constraint("fk_recon_investigation_closed_by", table, type_="foreignkey")
    op.drop_column(table, "resolution_quality_note")
    op.drop_column(table, "resolution_quality_reviewed_at")
    op.drop_column(table, "resolution_quality_reviewed_by_id")
    op.drop_column(table, "resolution_quality_status")
    op.drop_column(table, "reopen_count")
    op.drop_column(table, "closed_by_id")
