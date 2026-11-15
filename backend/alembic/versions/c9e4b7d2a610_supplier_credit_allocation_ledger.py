"""Add immutable supplier credit notes and invoice allocations.

Revision ID: c9e4b7d2a610
Revises: a8f4c2d9e610
"""
from alembic import op
import sqlalchemy as sa

revision = "c9e4b7d2a610"
down_revision = "a8f4c2d9e610"
branch_labels = None
depends_on = None

CREDIT_TABLE = "procurement_supplier_credit_notes"
ALLOCATION_TABLE = "procurement_supplier_credit_allocations"


def upgrade() -> None:
    amount_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        CREDIT_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("purchase_return_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", amount_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise >= 0", name="ck_supplier_credit_amount_nonnegative"),
        sa.UniqueConstraint("purchase_return_id", name="uq_supplier_credit_purchase_return"),
        sa.ForeignKeyConstraint(["purchase_return_id"], ["procurement_purchase_returns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_credit_vendor_created", CREDIT_TABLE, ["vendor_id", "created_at"])

    op.create_table(
        ALLOCATION_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("credit_note_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", amount_type, nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("allocated_by_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_credit_allocation_positive"),
        sa.UniqueConstraint("credit_note_id", "invoice_id", name="uq_supplier_credit_invoice"),
        sa.ForeignKeyConstraint(["credit_note_id"], [f"{CREDIT_TABLE}.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invoice_id"], ["procurement_vendor_invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["allocated_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_credit_allocation_invoice", ALLOCATION_TABLE, ["invoice_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_supplier_credit_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Supplier credit ledger records are append-only';
            END;
            $$ LANGUAGE plpgsql;
        """)
        for table in (CREDIT_TABLE, ALLOCATION_TABLE):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_supplier_credit_ledger_mutation();
            """)
    elif op.get_bind().dialect.name == "sqlite":
        for table in (CREDIT_TABLE, ALLOCATION_TABLE):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_update
                BEFORE UPDATE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Supplier credit ledger records are append-only'); END;
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_delete
                BEFORE DELETE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Supplier credit ledger records are append-only'); END;
            """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in (CREDIT_TABLE, ALLOCATION_TABLE):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION IF EXISTS prevent_supplier_credit_ledger_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for table in (CREDIT_TABLE, ALLOCATION_TABLE):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update")
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete")
    op.drop_index("ix_supplier_credit_allocation_invoice", table_name=ALLOCATION_TABLE)
    op.drop_table(ALLOCATION_TABLE)
    op.drop_index("ix_supplier_credit_vendor_created", table_name=CREDIT_TABLE)
    op.drop_table(CREDIT_TABLE)
