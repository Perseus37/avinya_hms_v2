"""Bank statement imports and supplier payment reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "b4d7e2a9c610"
down_revision = "a7c4e2d9f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    direction = sa.Enum("DEBIT", "CREDIT", name="bankstatementdirectionenum")
    direction.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "procurement_bank_statement_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bank_account_ref", sa.String(100), nullable=False),
        sa.Column("statement_reference", sa.String(120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("opening_balance_paise", sa.Integer(), nullable=False),
        sa.Column("closing_balance_paise", sa.Integer(), nullable=False),
        sa.Column("imported_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("period_end >= period_start", name="ck_bank_statement_period"),
        sa.UniqueConstraint("bank_account_ref", "statement_reference", name="uq_bank_statement_account_reference"),
        sa.ForeignKeyConstraint(["imported_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "procurement_bank_statement_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_ref", sa.String(100), nullable=False),
        sa.Column("bank_transaction_id", sa.String(150), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("direction", direction, nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("bank_reference", sa.String(150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_bank_statement_line_amount_positive"),
        sa.UniqueConstraint("bank_account_ref", "bank_transaction_id", name="uq_bank_statement_transaction"),
        sa.ForeignKeyConstraint(["batch_id"], ["procurement_bank_statement_batches.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_bank_statement_line_batch_date", "procurement_bank_statement_lines", ["batch_id", "transaction_date"])
    op.create_index("ix_bank_statement_line_reference", "procurement_bank_statement_lines", ["bank_reference"])
    op.create_table(
        "procurement_supplier_payment_bank_matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("statement_line_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("matched_by_id", sa.Integer(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_supplier_payment_bank_match_positive"),
        sa.ForeignKeyConstraint(["statement_line_id"], ["procurement_bank_statement_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_id"], ["procurement_supplier_payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["matched_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_supplier_payment_bank_match_payment", "procurement_supplier_payment_bank_matches", ["payment_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_payment_bank_match_payment", table_name="procurement_supplier_payment_bank_matches")
    op.drop_table("procurement_supplier_payment_bank_matches")
    op.drop_index("ix_bank_statement_line_reference", table_name="procurement_bank_statement_lines")
    op.drop_index("ix_bank_statement_line_batch_date", table_name="procurement_bank_statement_lines")
    op.drop_table("procurement_bank_statement_lines")
    op.drop_table("procurement_bank_statement_batches")
    sa.Enum(name="bankstatementdirectionenum").drop(op.get_bind(), checkfirst=True)
