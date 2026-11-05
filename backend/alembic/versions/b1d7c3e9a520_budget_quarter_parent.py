"""Allow quarterly allocations to roll up to an annual procurement budget."""

from alembic import op
import sqlalchemy as sa

revision = "b1d7c3e9a520"
down_revision = "a9c4e7d2f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("procurement_budgets") as batch_op:
        batch_op.add_column(sa.Column("parent_budget_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_procurement_budgets_parent_budget_id",
            "procurement_budgets",
            ["parent_budget_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_procurement_budgets_parent_budget_id", ["parent_budget_id"])


def downgrade() -> None:
    with op.batch_alter_table("procurement_budgets") as batch_op:
        batch_op.drop_index("ix_procurement_budgets_parent_budget_id")
        batch_op.drop_constraint("fk_procurement_budgets_parent_budget_id", type_="foreignkey")
        batch_op.drop_column("parent_budget_id")
