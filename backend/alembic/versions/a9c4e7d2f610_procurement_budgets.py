"""Add procurement budget allocations and maker-checker revisions."""

from alembic import op
import sqlalchemy as sa

revision = "a9c4e7d2f610"
down_revision = "f2a9c6d1e840"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("budget_number", sa.String(length=50), nullable=False),
        sa.Column("requesting_department_id", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(length=12), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("total_amount_paise", sa.Integer(), nullable=False),
        sa.Column("warning_threshold_pct", sa.Integer(), server_default="80", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="DRAFT", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("period_type IN ('ANNUAL', 'QUARTERLY')", name="ck_proc_budget_period_type"),
        sa.CheckConstraint("category IN ('PHARMACY', 'LABORATORY', 'GENERAL_SUPPLIES', 'EQUIPMENT', 'SERVICES', 'OTHER')", name="ck_proc_budget_category"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED')", name="ck_proc_budget_status"),
        sa.CheckConstraint("period_end >= period_start", name="ck_proc_budget_period_valid"),
        sa.CheckConstraint("total_amount_paise >= 0", name="ck_proc_budget_amount_non_neg"),
        sa.CheckConstraint("warning_threshold_pct >= 1 AND warning_threshold_pct <= 100", name="ck_proc_budget_warning_range"),
        sa.ForeignKeyConstraint(["requesting_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("budget_number", name="uq_procurement_budgets_budget_number"),
        sa.UniqueConstraint("requesting_department_id", "category", "period_start", "period_end", name="uq_proc_budget_department_category_period"),
    )
    op.create_index("ix_procurement_budgets_budget_number", "procurement_budgets", ["budget_number"], unique=True)
    op.create_index("ix_proc_budget_period_status", "procurement_budgets", ["period_start", "period_end", "status"])
    op.create_index("ix_proc_budget_department_category", "procurement_budgets", ["requesting_department_id", "category"])

    op.create_table(
        "procurement_budget_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("prior_amount_paise", sa.Integer(), nullable=False),
        sa.Column("proposed_amount_paise", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="PENDING", nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("proposed_amount_paise >= 0", name="ck_proc_budget_revision_amount_non_neg"),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_proc_budget_revision_status"),
        sa.ForeignKeyConstraint(["budget_id"], ["procurement_budgets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("budget_id", "revision_number", name="uq_proc_budget_revision_number"),
    )
    op.create_index("ix_proc_budget_revision_status", "procurement_budget_revisions", ["budget_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_proc_budget_revision_status", table_name="procurement_budget_revisions")
    op.drop_table("procurement_budget_revisions")
    op.drop_index("ix_proc_budget_department_category", table_name="procurement_budgets")
    op.drop_index("ix_proc_budget_period_status", table_name="procurement_budgets")
    op.drop_index("ix_procurement_budgets_budget_number", table_name="procurement_budgets")
    op.drop_table("procurement_budgets")
