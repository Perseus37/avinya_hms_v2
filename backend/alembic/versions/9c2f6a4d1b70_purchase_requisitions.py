"""Add external purchase requisitions and purchase-order traceability."""

from alembic import op
import sqlalchemy as sa


revision = "9c2f6a4d1b70"
down_revision = "7a91c4e2b630"
branch_labels = None
depends_on = None


purchase_requisition_status = sa.Enum(
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "PARTIALLY_ORDERED",
    "CONVERTED",
    "CANCELLED",
    name="purchaserequisitionstatusenum",
)


def upgrade() -> None:
    bind = op.get_bind()
    purchase_requisition_status.create(bind, checkfirst=True)

    op.create_table(
        "procurement_requisitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requisition_number", sa.String(length=50), nullable=False),
        sa.Column("requesting_department_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("status", purchase_requisition_status, nullable=False),
        sa.Column("required_by_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["requesting_department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requisition_number", name="uq_procurement_requisitions_number"),
    )
    op.create_index("ix_procurement_requisitions_requisition_number", "procurement_requisitions", ["requisition_number"], unique=True)
    op.create_index("ix_procurement_requisitions_requesting_department_id", "procurement_requisitions", ["requesting_department_id"])
    op.create_index("ix_procurement_requisitions_requested_by_id", "procurement_requisitions", ["requested_by_id"])
    op.create_index("ix_procurement_requisitions_reviewed_by_id", "procurement_requisitions", ["reviewed_by_id"])
    op.create_index("ix_proc_requisition_status_created", "procurement_requisitions", ["status", "created_at"])
    op.create_index("ix_proc_requisition_department_status", "procurement_requisitions", ["requesting_department_id", "status"])

    op.create_table(
        "procurement_requisition_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requisition_id", sa.Integer(), nullable=False),
        sa.Column("medication_id", sa.Integer(), nullable=True),
        sa.Column("item_description", sa.String(length=200), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("approved_quantity", sa.Integer(), nullable=True),
        sa.Column("estimated_unit_price_paise", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("requested_quantity > 0", name="ck_proc_req_item_qty_pos"),
        sa.CheckConstraint("approved_quantity IS NULL OR approved_quantity >= 0", name="ck_proc_req_item_approved_qty_nonneg"),
        sa.ForeignKeyConstraint(["requisition_id"], ["procurement_requisitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["medication_id"], ["medication_master.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_procurement_requisition_items_requisition_id", "procurement_requisition_items", ["requisition_id"])
    op.create_index("ix_procurement_requisition_items_medication_id", "procurement_requisition_items", ["medication_id"])
    op.create_index("ix_proc_req_items_requisition", "procurement_requisition_items", ["requisition_id"])

    op.add_column("procurement_purchase_orders", sa.Column("requisition_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_procurement_purchase_orders_requisition_id",
        "procurement_purchase_orders",
        "procurement_requisitions",
        ["requisition_id"],
        ["id"],
    )
    op.create_index("ix_procurement_purchase_orders_requisition_id", "procurement_purchase_orders", ["requisition_id"])

    op.add_column("procurement_po_items", sa.Column("requisition_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_procurement_po_items_requisition_item_id",
        "procurement_po_items",
        "procurement_requisition_items",
        ["requisition_item_id"],
        ["id"],
    )
    op.create_index("ix_procurement_po_items_requisition_item_id", "procurement_po_items", ["requisition_item_id"])


def downgrade() -> None:
    op.drop_index("ix_procurement_po_items_requisition_item_id", table_name="procurement_po_items")
    op.drop_constraint("fk_procurement_po_items_requisition_item_id", "procurement_po_items", type_="foreignkey")
    op.drop_column("procurement_po_items", "requisition_item_id")

    op.drop_index("ix_procurement_purchase_orders_requisition_id", table_name="procurement_purchase_orders")
    op.drop_constraint("fk_procurement_purchase_orders_requisition_id", "procurement_purchase_orders", type_="foreignkey")
    op.drop_column("procurement_purchase_orders", "requisition_id")

    op.drop_index("ix_proc_req_items_requisition", table_name="procurement_requisition_items")
    op.drop_index("ix_procurement_requisition_items_medication_id", table_name="procurement_requisition_items")
    op.drop_index("ix_procurement_requisition_items_requisition_id", table_name="procurement_requisition_items")
    op.drop_table("procurement_requisition_items")

    op.drop_index("ix_proc_requisition_department_status", table_name="procurement_requisitions")
    op.drop_index("ix_proc_requisition_status_created", table_name="procurement_requisitions")
    op.drop_index("ix_procurement_requisitions_reviewed_by_id", table_name="procurement_requisitions")
    op.drop_index("ix_procurement_requisitions_requested_by_id", table_name="procurement_requisitions")
    op.drop_index("ix_procurement_requisitions_requesting_department_id", table_name="procurement_requisitions")
    op.drop_index("ix_procurement_requisitions_requisition_number", table_name="procurement_requisitions")
    op.drop_table("procurement_requisitions")

    purchase_requisition_status.drop(op.get_bind(), checkfirst=True)
