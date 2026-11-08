"""Add supplier payment ledger and independently approved payment requests.

Revision ID: f2a9c7d1e520
Revises: e1a3c7b5d902
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a9c7d1e520"
down_revision = "e1a3c7b5d902"
branch_labels = None
depends_on = None

payment_method = sa.Enum(
    "BANK_TRANSFER", "UPI", "CHEQUE", "CASH", "CARD", "NEFT", "RTGS", "IMPS", "OTHER",
    name="supplierpaymentmethodenum",
)


def upgrade() -> None:
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
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_amount_positive"),
        sa.UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_vendor_reference"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_supplier_payment_vendor_date",
        "procurement_supplier_payments",
        ["vendor_id", "payment_date"],
    )
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
    op.create_index(
        "ix_supplier_payment_allocation_invoice",
        "procurement_supplier_payment_allocations",
        ["invoice_id"],
    )
    op.create_table(
        "procurement_supplier_payment_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("payment_reference", sa.String(100), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("executed_payment_id", sa.Integer(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_amount_positive"),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','EXECUTED','CANCELLED')",
            name="ck_supplier_payment_request_status",
        ),
        sa.UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_request_reference"),
        sa.UniqueConstraint("executed_payment_id", name="uq_supplier_payment_request_executed_payment"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["executed_payment_id"], ["procurement_supplier_payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_supplier_payment_request_status_date",
        "procurement_supplier_payment_requests",
        ["status", "scheduled_date"],
    )
    op.create_table(
        "procurement_supplier_payment_request_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_allocation_positive"),
        sa.UniqueConstraint("request_id", "invoice_id", name="uq_supplier_payment_request_invoice"),
        sa.ForeignKeyConstraint(["request_id"], ["procurement_supplier_payment_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_supplier_payment_request_allocation_invoice",
        "procurement_supplier_payment_request_allocations",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_payment_request_allocation_invoice", table_name="procurement_supplier_payment_request_allocations")
    op.drop_table("procurement_supplier_payment_request_allocations")
    op.drop_index("ix_supplier_payment_request_status_date", table_name="procurement_supplier_payment_requests")
    op.drop_table("procurement_supplier_payment_requests")
    op.drop_index("ix_supplier_payment_allocation_invoice", table_name="procurement_supplier_payment_allocations")
    op.drop_table("procurement_supplier_payment_allocations")
    op.drop_index("ix_supplier_payment_vendor_date", table_name="procurement_supplier_payments")
    op.drop_table("procurement_supplier_payments")
    payment_method.drop(op.get_bind(), checkfirst=True)
