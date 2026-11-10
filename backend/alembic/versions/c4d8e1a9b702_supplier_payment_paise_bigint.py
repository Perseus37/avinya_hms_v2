"""Widen supplier-payment and bank-reconciliation paise columns.

Revision ID: c4d8e1a9b702
Revises: b7e4c9d2a610
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d8e1a9b702"
down_revision = "b7e4c9d2a610"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("procurement_supplier_payments", "amount_paise"),
    ("procurement_supplier_payment_allocations", "amount_paise"),
    ("procurement_supplier_payment_requests", "amount_paise"),
    ("procurement_supplier_payment_request_allocations", "amount_paise"),
    ("procurement_bank_statement_batches", "opening_balance_paise"),
    ("procurement_bank_statement_batches", "closing_balance_paise"),
    ("procurement_bank_statement_lines", "amount_paise"),
    ("procurement_supplier_payment_bank_matches", "amount_paise"),
)


def upgrade() -> None:
    # SQLite INTEGER is already a signed 64-bit storage class. Avoid table
    # recreation so the append-only triggers remain intact.
    if op.get_bind().dialect.name == "postgresql":
        for table_name, column_name in _COLUMNS:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=False,
            )


def downgrade() -> None:
    # Narrowing can silently overflow or fail for legitimate production values.
    # Deliberately irreversible: retain the wider representation.
    pass
