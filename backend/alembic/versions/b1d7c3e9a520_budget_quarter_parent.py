"""Allow quarterly allocations to roll up to an annual procurement budget."""

from alembic import op
import sqlalchemy as sa

revision = "b1d7c3e9a520"
down_revision = "a9c4e7d2f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_budgets",
        sa.Column("parent_budget_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_procurement_budgets_parent_budget_id",
        "procurement_budgets",
        "procurement_budgets",
        ["parent_budget_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_procurement_budgets_parent_budget_id",
        "procurement_budgets",
        ["parent_budget_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_procurement_budgets_parent_budget_id", table_name="procurement_budgets")
    op.drop_constraint("fk_procurement_budgets_parent_budget_id", "procurement_budgets", type_="foreignkey")
    op.drop_column("procurement_budgets", "parent_budget_id")
