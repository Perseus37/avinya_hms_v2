"""Add immutable bank statement imports and supplier payment matches.

Revision ID: a7c4e9d2f610
Revises: f2a9c7d1e520
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c4e9d2f610"
down_revision = "f2a9c7d1e520"
branch_labels = None
depends_on = None


IMMUTABLE_TABLES = (
    "procurement_bank_statement_batches",
    "procurement_bank_statement_lines",
    "procurement_supplier_payment_bank_matches",
)


def upgrade() -> None:
    op.create_table(
        "procurement_bank_statement_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_key", sa.String(64), nullable=False),
        sa.Column("account_label", sa.String(80), nullable=True),
        sa.Column("statement_reference", sa.String(120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("opening_balance_paise", sa.Integer(), nullable=False),
        sa.Column("closing_balance_paise", sa.Integer(), nullable=False),
        sa.Column("imported_by_id", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("period_end >= period_start", name="ck_bank_statement_period_valid"),
        sa.CheckConstraint("opening_balance_paise >= 0", name="ck_bank_statement_opening_nonnegative"),
        sa.CheckConstraint("closing_balance_paise >= 0", name="ck_bank_statement_closing_nonnegative"),
        sa.UniqueConstraint("account_key", "statement_reference", name="uq_bank_statement_account_reference"),
        sa.ForeignKeyConstraint(["imported_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_bank_statement_period", "procurement_bank_statement_batches", ["period_start", "period_end"])
    op.create_index("ix_bank_statement_imported_by", "procurement_bank_statement_batches", ["imported_by_id"])

    op.create_table(
        "procurement_bank_statement_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("account_key", sa.String(64), nullable=False),
        sa.Column("bank_transaction_id", sa.String(160), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("bank_reference", sa.String(160), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_bank_statement_direction"),
        sa.CheckConstraint("amount_paise > 0", name="ck_bank_statement_amount_positive"),
        sa.UniqueConstraint("account_key", "bank_transaction_id", name="uq_bank_statement_transaction_identity"),
        sa.ForeignKeyConstraint(["batch_id"], ["procurement_bank_statement_batches.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_bank_statement_line_batch_date", "procurement_bank_statement_lines", ["batch_id", "transaction_date"])
    op.create_index("ix_bank_statement_line_direction_date", "procurement_bank_statement_lines", ["direction", "transaction_date"])

    op.create_table(
        "procurement_supplier_payment_bank_matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("statement_line_id", sa.Integer(), nullable=False),
        sa.Column("supplier_payment_id", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("matched_by_id", sa.Integer(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_bank_match_amount_positive"),
        sa.UniqueConstraint("statement_line_id", "supplier_payment_id", name="uq_bank_match_line_payment"),
        sa.ForeignKeyConstraint(["statement_line_id"], ["procurement_bank_statement_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_payment_id"], ["procurement_supplier_payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["matched_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_bank_match_payment", "procurement_supplier_payment_bank_matches", ["supplier_payment_id"])
    op.create_index("ix_bank_match_actor_time", "procurement_supplier_payment_bank_matches", ["matched_by_id", "matched_at"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_bank_reconciliation_mutation()
            RETURNS trigger AS $fn$
            BEGIN
                RAISE EXCEPTION 'Bank statement and reconciliation records are append-only';
            END;
            $fn$ LANGUAGE plpgsql
        """)
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"""
                CREATE TRIGGER trg_{table_name}_immutable
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION prevent_bank_reconciliation_mutation()
            """)
    elif bind.dialect.name == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"""
                CREATE TRIGGER trg_{table_name}_immutable_update
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'Bank statement and reconciliation records are append-only');
                END
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table_name}_immutable_delete
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(ABORT, 'Bank statement and reconciliation records are append-only');
                END
            """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
        op.execute("DROP FUNCTION IF EXISTS prevent_bank_reconciliation_mutation()")
    elif bind.dialect.name == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable_update")
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable_delete")

    op.drop_index("ix_bank_match_actor_time", table_name="procurement_supplier_payment_bank_matches")
    op.drop_index("ix_bank_match_payment", table_name="procurement_supplier_payment_bank_matches")
    op.drop_table("procurement_supplier_payment_bank_matches")
    op.drop_index("ix_bank_statement_line_direction_date", table_name="procurement_bank_statement_lines")
    op.drop_index("ix_bank_statement_line_batch_date", table_name="procurement_bank_statement_lines")
    op.drop_table("procurement_bank_statement_lines")
    op.drop_index("ix_bank_statement_imported_by", table_name="procurement_bank_statement_batches")
    op.drop_index("ix_bank_statement_period", table_name="procurement_bank_statement_batches")
    op.drop_table("procurement_bank_statement_batches")
