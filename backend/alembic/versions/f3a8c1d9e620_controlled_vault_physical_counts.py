"""Add dual-witness controlled-vault physical reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "f3a8c1d9e620"
down_revision = "e7a4c9d2f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "controlled_vault_counts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vault_id", sa.Integer(), sa.ForeignKey("controlled_substance_vaults.id"), nullable=False),
        sa.Column("expected_balance", sa.Integer(), nullable=False),
        sa.Column("physical_balance", sa.Integer(), nullable=False),
        sa.Column("snapshot_movement_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("counted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("witness_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="PENDING", nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("expected_balance >= 0 AND physical_balance >= 0", name="ck_controlled_vault_count_nonnegative"),
    )
    op.create_index("ix_controlled_vault_counts_vault_id", "controlled_vault_counts", ["vault_id"])
    op.create_index("ix_controlled_vault_counts_vault_status", "controlled_vault_counts", ["vault_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_controlled_vault_counts_vault_status", table_name="controlled_vault_counts")
    op.drop_index("ix_controlled_vault_counts_vault_id", table_name="controlled_vault_counts")
    op.drop_table("controlled_vault_counts")
