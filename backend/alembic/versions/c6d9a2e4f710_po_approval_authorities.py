"""Add role-based purchase-order approval limits."""
from alembic import op
import sqlalchemy as sa

revision = "c6d9a2e4f710"
down_revision = "b4e7c2a91d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_po_approval_authorities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("max_amount_paise", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("max_amount_paise >= 0", name="ck_po_approval_limit_non_neg"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id"),
    )


def downgrade() -> None:
    op.drop_table("procurement_po_approval_authorities")
