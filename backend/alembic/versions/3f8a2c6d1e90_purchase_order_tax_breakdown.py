"""Preserve tax-inclusive commercial values on purchase orders."""
from alembic import op
import sqlalchemy as sa

revision = "3f8a2c6d1e90"
down_revision = "e2c7a9d4f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing PO totals were pre-tax. Preserve their historical meaning by
    # backfilling subtotal=old total and tax=0; do not invent historic tax.
    op.add_column(
        "procurement_purchase_orders",
        sa.Column("subtotal_paise", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "procurement_purchase_orders",
        sa.Column("tax_amount_paise", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE procurement_purchase_orders "
        "SET subtotal_paise = total_amount_paise, tax_amount_paise = 0"
    )

    op.add_column(
        "procurement_po_items",
        sa.Column("tax_percentage", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "procurement_po_items",
        sa.Column("tax_amount_paise", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "procurement_po_items",
        sa.Column("gross_total_paise", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE procurement_po_items "
        "SET tax_percentage = 0, tax_amount_paise = 0, "
        "gross_total_paise = total_price_paise"
    )

    op.add_column(
        "procurement_supplier_quotation_items",
        sa.Column("tax_amount_paise", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE procurement_supplier_quotation_items "
        "SET tax_amount_paise = "
        "((quantity_quoted * unit_price_paise * tax_percentage + 50) / 100)"
    )
    op.create_check_constraint(
        "ck_proc_quote_tax_non_neg", "procurement_supplier_quotation_items",
        "tax_amount_paise >= 0",
    )
    op.create_check_constraint(
        "ck_proc_quote_line_total", "procurement_supplier_quotation_items",
        "line_total_paise = quantity_quoted * unit_price_paise + tax_amount_paise",
    )

    op.create_check_constraint(
        "ck_po_subtotal_non_neg", "procurement_purchase_orders", "subtotal_paise >= 0"
    )
    op.create_check_constraint(
        "ck_po_tax_non_neg", "procurement_purchase_orders", "tax_amount_paise >= 0"
    )
    op.create_check_constraint(
        "ck_po_financial_totals", "procurement_purchase_orders",
        "subtotal_paise + tax_amount_paise = total_amount_paise",
    )
    op.create_check_constraint(
        "ck_po_item_tax_range", "procurement_po_items",
        "tax_percentage >= 0 AND tax_percentage <= 100",
    )
    op.create_check_constraint(
        "ck_po_item_tax_non_neg", "procurement_po_items", "tax_amount_paise >= 0"
    )
    op.create_check_constraint(
        "ck_po_item_gross_non_neg", "procurement_po_items", "gross_total_paise >= 0"
    )
    op.create_check_constraint(
        "ck_po_item_financial_totals", "procurement_po_items",
        "total_price_paise + tax_amount_paise = gross_total_paise",
    )

    for table, column in [
        ("procurement_purchase_orders", "subtotal_paise"),
        ("procurement_purchase_orders", "tax_amount_paise"),
        ("procurement_po_items", "tax_percentage"),
        ("procurement_po_items", "tax_amount_paise"),
        ("procurement_po_items", "gross_total_paise"),
        ("procurement_supplier_quotation_items", "tax_amount_paise"),
    ]:
        op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_proc_quote_line_total", "procurement_supplier_quotation_items", type_="check")
    op.drop_constraint("ck_proc_quote_tax_non_neg", "procurement_supplier_quotation_items", type_="check")
    op.drop_column("procurement_supplier_quotation_items", "tax_amount_paise")
    op.drop_constraint("ck_po_item_financial_totals", "procurement_po_items", type_="check")
    op.drop_constraint("ck_po_item_gross_non_neg", "procurement_po_items", type_="check")
    op.drop_constraint("ck_po_item_tax_non_neg", "procurement_po_items", type_="check")
    op.drop_constraint("ck_po_item_tax_range", "procurement_po_items", type_="check")
    op.drop_constraint("ck_po_financial_totals", "procurement_purchase_orders", type_="check")
    op.drop_constraint("ck_po_tax_non_neg", "procurement_purchase_orders", type_="check")
    op.drop_constraint("ck_po_subtotal_non_neg", "procurement_purchase_orders", type_="check")
    op.drop_column("procurement_po_items", "gross_total_paise")
    op.drop_column("procurement_po_items", "tax_amount_paise")
    op.drop_column("procurement_po_items", "tax_percentage")
    op.drop_column("procurement_purchase_orders", "tax_amount_paise")
    op.drop_column("procurement_purchase_orders", "subtotal_paise")
