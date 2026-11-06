"""Supplier credit/debit adjustments and supplier advance allocations."""
from alembic import op
import sqlalchemy as sa

revision = "a7c4e2d9f610"
down_revision = "f1c8a4d7e920"
branch_labels = None
depends_on = None


def upgrade() -> None:
    adjustment_type = sa.Enum("SUPPLIER_CREDIT_NOTE", "HOSPITAL_DEBIT_NOTE", name="supplieradjustmenttypeenum")
    adjustment_status = sa.Enum("PENDING", "APPROVED", "REJECTED", name="supplieradjustmentstatusenum")
    payment_method = sa.Enum("BANK_TRANSFER", "UPI", "CHEQUE", "CASH", "CARD", "NEFT", "RTGS", "IMPS", "OTHER", name="supplierpaymentmethodenum")
    adjustment_type.create(op.get_bind(), checkfirst=True)
    adjustment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "procurement_supplier_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("adjustment_type", adjustment_type, nullable=False),
        sa.Column("document_number", sa.String(100), nullable=False),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", adjustment_status, nullable=False, server_default="PENDING"),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_adjustment_amount_positive"),
        sa.UniqueConstraint("vendor_id", "adjustment_type", "document_number", name="uq_supplier_adjustment_document"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_adjustment_vendor_date", "procurement_supplier_adjustments", ["vendor_id", "document_date"])
    op.create_index("ix_supplier_adjustment_status", "procurement_supplier_adjustments", ["status"])
    op.create_table(
        "procurement_supplier_adjustment_applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("adjustment_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_adjustment_application_positive"),
        sa.UniqueConstraint("adjustment_id", "invoice_id", name="uq_supplier_adjustment_invoice"),
        sa.ForeignKeyConstraint(["adjustment_id"], ["procurement_supplier_adjustments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_adjustment_application_invoice", "procurement_supplier_adjustment_applications", ["invoice_id"])
    op.create_table(
        "procurement_supplier_advances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("advance_reference", sa.String(100), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("advance_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_advance_amount_positive"),
        sa.UniqueConstraint("vendor_id", "advance_reference", name="uq_supplier_advance_reference"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_advance_vendor_date", "procurement_supplier_advances", ["vendor_id", "advance_date"])
    op.create_table(
        "procurement_supplier_advance_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("advance_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_advance_allocation_positive"),
        sa.UniqueConstraint("advance_id", "invoice_id", name="uq_supplier_advance_invoice"),
        sa.ForeignKeyConstraint(["advance_id"], ["procurement_supplier_advances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_advance_allocation_invoice", "procurement_supplier_advance_allocations", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_advance_allocation_invoice", table_name="procurement_supplier_advance_allocations")
    op.drop_table("procurement_supplier_advance_allocations")
    op.drop_index("ix_supplier_advance_vendor_date", table_name="procurement_supplier_advances")
    op.drop_table("procurement_supplier_advances")
    op.drop_index("ix_supplier_adjustment_application_invoice", table_name="procurement_supplier_adjustment_applications")
    op.drop_table("procurement_supplier_adjustment_applications")
    op.drop_index("ix_supplier_adjustment_status", table_name="procurement_supplier_adjustments")
    op.drop_index("ix_supplier_adjustment_vendor_date", table_name="procurement_supplier_adjustments")
    op.drop_table("procurement_supplier_adjustments")
    sa.Enum(name="supplieradjustmentstatusenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="supplieradjustmenttypeenum").drop(op.get_bind(), checkfirst=True)
