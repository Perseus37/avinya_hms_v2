"""Record patient-indent issue allocations and append-only returns.

Revision ID: e8a4c1d7f620
Revises: b7e4c9d2a610
"""
from alembic import op
import sqlalchemy as sa

revision = "e8a4c1d7f620"
down_revision = "b7e4c9d2a610"
branch_labels = None
depends_on = None

ALLOCATIONS = "procurement_patient_indent_issue_allocations"
RETURNS = "procurement_patient_indent_return_events"


def upgrade() -> None:
    op.create_table(
        ALLOCATIONS,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("indent_item_id", sa.Integer(), nullable=False),
        sa.Column("inventory_batch_id", sa.Integer(), nullable=False),
        sa.Column("invoice_line_item_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["invoice_line_item_id"], ["invoice_line_items.id"], ondelete="RESTRICT"),
        sa.Column("issued_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("issued_quantity > 0", name="ck_patient_indent_alloc_issued_pos"),
        sa.ForeignKeyConstraint(["indent_item_id"], ["procurement_indent_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inventory_batch_id"], ["inventory_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_patient_indent_alloc_item_batch", ALLOCATIONS, ["indent_item_id", "inventory_batch_id"])
    op.create_table(
        RETURNS,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("allocation_id", sa.Integer(), nullable=False),
        sa.Column("return_quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("return_quantity > 0", name="ck_patient_indent_return_qty_pos"),
        sa.ForeignKeyConstraint(["allocation_id"], [f"{ALLOCATIONS}.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_patient_indent_return_allocation", RETURNS, ["allocation_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_patient_indent_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Patient indent issue and return provenance is immutable';
            END;
            $$ LANGUAGE plpgsql;
        """)
        for table in (ALLOCATIONS, RETURNS):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_patient_indent_ledger_mutation();
            """)
    elif op.get_bind().dialect.name == "sqlite":
        for table in (ALLOCATIONS, RETURNS):
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_update
                BEFORE UPDATE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Patient indent issue and return provenance is immutable'); END;
            """)
            op.execute(f"""
                CREATE TRIGGER trg_{table}_immutable_delete
                BEFORE DELETE ON {table}
                BEGIN SELECT RAISE(ABORT, 'Patient indent issue and return provenance is immutable'); END;
            """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in (ALLOCATIONS, RETURNS):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION IF EXISTS prevent_patient_indent_ledger_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for table in (ALLOCATIONS, RETURNS):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update")
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete")
    op.drop_index("ix_patient_indent_return_allocation", table_name=RETURNS)
    op.drop_table(RETURNS)
    op.drop_index("ix_patient_indent_alloc_item_batch", table_name=ALLOCATIONS)
    op.drop_table(ALLOCATIONS)
