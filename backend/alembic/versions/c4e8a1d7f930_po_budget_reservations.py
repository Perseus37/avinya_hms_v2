"""Add PO-line budget classification and immutable reservation/receipt ledger."""

from alembic import op
import sqlalchemy as sa

revision = "c4e8a1d7f930"
down_revision = "b1d7c3e9a520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("procurement_po_items") as batch_op:
        batch_op.add_column(sa.Column("budget_department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("budget_category", sa.String(length=24), server_default="GENERAL_SUPPLIES", nullable=False))
        batch_op.add_column(sa.Column("budget_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_proc_po_item_budget_department",
            "departments",
            ["budget_department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_proc_po_item_budget_id",
            "procurement_budgets",
            ["budget_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_proc_po_item_budget_category",
            "budget_category IN ('PHARMACY', 'LABORATORY', 'GENERAL_SUPPLIES', 'EQUIPMENT', 'SERVICES', 'OTHER')",
        )
        batch_op.create_index("ix_proc_po_items_budget_department_id", ["budget_department_id"])
        batch_op.create_index("ix_proc_po_items_budget_id", ["budget_id"])

    op.create_table(
        "procurement_budget_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("po_item_id", sa.Integer(), nullable=True),
        sa.Column("grn_item_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(length=16), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("reference_key", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("movement_type IN ('RESERVATION', 'RELEASE', 'RECEIPT')", name="ck_proc_budget_movement_type"),
        sa.CheckConstraint("amount_paise > 0", name="ck_proc_budget_movement_amount_positive"),
        sa.ForeignKeyConstraint(["budget_id"], ["procurement_budgets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["po_id"], ["procurement_purchase_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("reference_key", name="uq_proc_budget_movement_reference"),
    )
    op.create_index("ix_proc_budget_movement_budget_type", "procurement_budget_movements", ["budget_id", "movement_type"])
    op.create_index("ix_proc_budget_movement_po", "procurement_budget_movements", ["po_id"])


def downgrade() -> None:
    op.drop_index("ix_proc_budget_movement_po", table_name="procurement_budget_movements")
    op.drop_index("ix_proc_budget_movement_budget_type", table_name="procurement_budget_movements")
    op.drop_table("procurement_budget_movements")
    with op.batch_alter_table("procurement_po_items") as batch_op:
        batch_op.drop_index("ix_proc_po_items_budget_id")
        batch_op.drop_index("ix_proc_po_items_budget_department_id")
        batch_op.drop_constraint("ck_proc_po_item_budget_category", type_="check")
        batch_op.drop_constraint("fk_proc_po_item_budget_id", type_="foreignkey")
        batch_op.drop_constraint("fk_proc_po_item_budget_department", type_="foreignkey")
        batch_op.drop_column("budget_id")
        batch_op.drop_column("budget_category")
        batch_op.drop_column("budget_department_id")
