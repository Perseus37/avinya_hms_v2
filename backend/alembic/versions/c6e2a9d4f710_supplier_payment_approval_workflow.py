"""Supplier payment request approval, scheduling, and execution."""
from alembic import op
import sqlalchemy as sa

revision = "c6e2a9d4f710"
down_revision = "b4d7e2a9c610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_supplier_payment_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("payment_reference", sa.String(100), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("BANK_TRANSFER", "UPI", "CHEQUE", "CASH", "CARD", "NEFT", "RTGS", "IMPS", "OTHER", name="supplierpaymentmethodenum", create_type=False),
            nullable=False,
        ),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("payment_run_reference", sa.String(100), nullable=True),
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_amount_positive"),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','EXECUTED','CANCELLED')", name="ck_supplier_payment_request_status"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["executed_payment_id"], ["procurement_supplier_payments.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_supplier_payment_request_reference",
        "procurement_supplier_payment_requests",
        ["vendor_id", "payment_reference"],
        unique=True,
    )
    op.create_index(
        "ix_supplier_payment_request_status_date",
        "procurement_supplier_payment_requests",
        ["status", "scheduled_date"],
    )
    op.create_index(
        "ix_supplier_payment_request_run",
        "procurement_supplier_payment_requests",
        ["payment_run_reference"],
    )
    op.create_table(
        "procurement_supplier_payment_request_allocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_allocation_positive"),
        sa.ForeignKeyConstraint(["request_id"], ["procurement_supplier_payment_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("request_id", "invoice_id", name="uq_supplier_payment_request_invoice"),
    )
    op.create_index(
        "ix_supplier_payment_request_allocation_invoice",
        "procurement_supplier_payment_request_allocations",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_payment_request_allocation_invoice", table_name="procurement_supplier_payment_request_allocations")
    op.drop_table("procurement_supplier_payment_request_allocations")
    op.drop_index("ix_supplier_payment_request_run", table_name="procurement_supplier_payment_requests")
    op.drop_index("ix_supplier_payment_request_status_date", table_name="procurement_supplier_payment_requests")
    op.drop_index("uq_supplier_payment_request_reference", table_name="procurement_supplier_payment_requests")
    op.drop_table("procurement_supplier_payment_requests")
