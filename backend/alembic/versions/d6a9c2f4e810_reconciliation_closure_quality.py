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


TABLE = "procurement_reconciliation_investigations"


def upgrade() -> None:
    # Batch mode keeps the additive migration compatible with SQLite test databases
    # while producing normal ALTER TABLE operations on PostgreSQL.
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("closed_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("resolution_quality_status", sa.String(16), nullable=False, server_default="NOT_REVIEWED"))
        batch.add_column(sa.Column("resolution_quality_reviewed_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resolution_quality_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("resolution_quality_note", sa.Text(), nullable=True))
        batch.create_foreign_key("fk_recon_investigation_closed_by", "users", ["closed_by_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_recon_investigation_quality_reviewer", "users", ["resolution_quality_reviewed_by_id"], ["id"], ondelete="SET NULL")
        batch.create_check_constraint("ck_recon_investigation_reopen_count_nonneg", "reopen_count >= 0")
        batch.create_check_constraint("ck_recon_investigation_quality_status", "resolution_quality_status IN ('NOT_REVIEWED','APPROVED','REJECTED')")
    batch_op = op
    batch_op.create_index("ix_recon_investigation_closed_by", TABLE, ["closed_by_id"])
    batch_op.create_index("ix_recon_investigation_quality_reviewer", TABLE, ["resolution_quality_reviewed_by_id"])


def downgrade() -> None:
    op.drop_index("ix_recon_investigation_quality_reviewer", table_name=TABLE)
    op.drop_index("ix_recon_investigation_closed_by", table_name=TABLE)
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("ck_recon_investigation_quality_status", type_="check")
        batch.drop_constraint("ck_recon_investigation_reopen_count_nonneg", type_="check")
        batch.drop_constraint("fk_recon_investigation_quality_reviewer", type_="foreignkey")
        batch.drop_constraint("fk_recon_investigation_closed_by", type_="foreignkey")
        batch.drop_column("resolution_quality_note")
        batch.drop_column("resolution_quality_reviewed_at")
        batch.drop_column("resolution_quality_reviewed_by_id")
        batch.drop_column("resolution_quality_status")
        batch.drop_column("reopen_count")
        batch.drop_column("closed_by_id")
