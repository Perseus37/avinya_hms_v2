"""Snapshot procurement units on quotation, PO, GRN and invoice lines."""

from alembic import op
import sqlalchemy as sa

revision = "b6d3a9e1f420"
down_revision = "a4c7e2b91d60"
branch_labels = None
depends_on = None

TABLES = (
    "procurement_supplier_quotation_items",
    "procurement_po_items",
    "procurement_grn_items",
    "procurement_vendor_invoice_items",
)

def upgrade() -> None:
    with op.batch_alter_table("procurement_requisition_items") as batch_op:
        batch_op.add_column(sa.Column("purchase_uom_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_proc_req_item_purchase_uom",
            "procurement_units_of_measure",
            ["purchase_uom_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    for table in TABLES:
        op.add_column(table, sa.Column("purchase_uom_code", sa.String(length=24), nullable=True))
        op.add_column(table, sa.Column("base_uom_code", sa.String(length=24), nullable=True))
        op.add_column(table, sa.Column("units_per_purchase_unit", sa.Numeric(18, 6), nullable=True))
        op.add_column(table, sa.Column("base_quantity", sa.Numeric(20, 6), nullable=True))
        op.add_column(table, sa.Column("base_unit_price_paise", sa.Numeric(24, 8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("procurement_requisition_items") as batch_op:
        batch_op.drop_constraint("fk_proc_req_item_purchase_uom", type_="foreignkey")
        batch_op.drop_column("purchase_uom_id")
    for table in reversed(TABLES):
        op.drop_column(table, "base_unit_price_paise")
        op.drop_column(table, "base_quantity")
        op.drop_column(table, "units_per_purchase_unit")
        op.drop_column(table, "base_uom_code")
        op.drop_column(table, "purchase_uom_code")
