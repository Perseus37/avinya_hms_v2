"""Add supplier quotation collection and selection audit."""
from alembic import op
import sqlalchemy as sa

revision = "b4e7c2a91d60"
down_revision = "9c2f6a4d1b70"
branch_labels = None
depends_on = None

quotation_status = sa.Enum(
    "RECEIVED", "SELECTED", "NOT_SELECTED", "WITHDRAWN",
    name="supplierquotationstatusenum",
)


def upgrade() -> None:
    quotation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "procurement_supplier_quotations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requisition_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("quotation_number", sa.String(100), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", quotation_status, nullable=False),
        sa.Column("selected_by_id", sa.Integer(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("total_amount_paise >= 0", name="ck_proc_quote_total_non_neg"),
        sa.ForeignKeyConstraint(["requisition_id"], ["procurement_requisitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"]),
        sa.ForeignKeyConstraint(["selected_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor_id", "quotation_number", name="uq_proc_quote_vendor_number"),
    )
    op.create_index("ix_procurement_supplier_quotations_requisition_id", "procurement_supplier_quotations", ["requisition_id"])
    op.create_index("ix_procurement_supplier_quotations_vendor_id", "procurement_supplier_quotations", ["vendor_id"])
    op.create_index("ix_proc_quote_requisition_status", "procurement_supplier_quotations", ["requisition_id", "status"])
    op.create_table(
        "procurement_supplier_quotation_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("requisition_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity_quoted", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column("tax_percentage", sa.Integer(), nullable=False),
        sa.Column("line_total_paise", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("quantity_quoted > 0", name="ck_proc_quote_qty_pos"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_proc_quote_price_non_neg"),
        sa.CheckConstraint("tax_percentage >= 0 AND tax_percentage <= 100", name="ck_proc_quote_tax_range"),
        sa.ForeignKeyConstraint(["quotation_id"], ["procurement_supplier_quotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisition_item_id"], ["procurement_requisition_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quotation_id", "requisition_item_id", name="uq_proc_quote_item_line"),
    )
    op.create_index("ix_procurement_supplier_quotation_items_quotation_id", "procurement_supplier_quotation_items", ["quotation_id"])
    op.create_index("ix_procurement_supplier_quotation_items_requisition_item_id", "procurement_supplier_quotation_items", ["requisition_item_id"])


def downgrade() -> None:
    op.drop_index("ix_procurement_supplier_quotation_items_requisition_item_id", table_name="procurement_supplier_quotation_items")
    op.drop_index("ix_procurement_supplier_quotation_items_quotation_id", table_name="procurement_supplier_quotation_items")
    op.drop_table("procurement_supplier_quotation_items")
    op.drop_index("ix_proc_quote_requisition_status", table_name="procurement_supplier_quotations")
    op.drop_index("ix_procurement_supplier_quotations_vendor_id", table_name="procurement_supplier_quotations")
    op.drop_index("ix_procurement_supplier_quotations_requisition_id", table_name="procurement_supplier_quotations")
    op.drop_table("procurement_supplier_quotations")
    quotation_status.drop(op.get_bind(), checkfirst=True)
