"""Add supplier payment ledger and invoice allocations."""
from alembic import op
import sqlalchemy as sa

revision = "f1c8a4d7e920"
down_revision = "e6b9c2d4a710"
branch_labels = None
depends_on = None


def upgrade() -> None:
    payment_method = sa.Enum(
        "BANK_TRANSFER", "UPI", "CHEQUE", "CASH", "CARD", "NEFT", "RTGS", "IMPS", "OTHER",
        name="supplierpaymentmethodenum",
    )
    payment_method.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "procurement_supplier_payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("payment_reference", sa.String(100), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_amount_positive"),
        sa.UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_vendor_reference"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_payment_vendor_date", "procurement_supplier_payments", ["vendor_id", "payment_date"])
    op.create_table(
        "procurement_supplier_payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_allocation_positive"),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_supplier_payment_invoice_allocation"),
        sa.ForeignKeyConstraint(["payment_id"], ["procurement_supplier_payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_payment_allocation_invoice", "procurement_supplier_payment_allocations", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_payment_allocation_invoice", table_name="procurement_supplier_payment_allocations")
    op.drop_table("procurement_supplier_payment_allocations")
    op.drop_index("ix_supplier_payment_vendor_date", table_name="procurement_supplier_payments")
    op.drop_table("procurement_supplier_payments")
    sa.Enum(name="supplierpaymentmethodenum").drop(op.get_bind(), checkfirst=True)
