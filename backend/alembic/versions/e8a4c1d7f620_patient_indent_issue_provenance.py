"""Record patient-indent issue allocations and append-only returns.

Revision ID: e8a4c1d7f620
Revises: e1a3c7b5d902
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8a4c1d7f620"
down_revision = "d2b6e8f1a903"
branch_labels = None
depends_on = None

ALLOCATIONS = "procurement_patient_indent_issue_allocations"
RETURNS = "procurement_patient_indent_return_events"


def upgrade() -> None:
    # Keep the PostgreSQL enum aligned with the partial-fulfilment state now
    # emitted by the patient-indent issue workflow. SQLite stores this as text.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE indentstatusenum ADD VALUE IF NOT EXISTS 'PARTIALLY_FULFILLED'")

    # PostgreSQL ORM metadata uses the native indentstatusenum type.
    # Widening a VARCHAR alone leaves schema parity broken; cast the existing
    # labels into the enum after ensuring the new partial-fulfilment label exists.
    if op.get_bind().dialect.name == "postgresql":
        indent_status_enum = postgresql.ENUM(
            "PENDING",
            "APPROVED",
            "PARTIALLY_FULFILLED",
            "FULFILLED",
            "CANCELLED",
            name="indentstatusenum",
            create_type=False,
        )
        op.alter_column(
            "procurement_indents",
            "status",
            existing_type=sa.String(length=19),
            type_=indent_status_enum,
            postgresql_using="status::text::indentstatusenum",
            existing_nullable=False,
        )
    elif op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("procurement_indents") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.String(length=9),
                type_=sa.String(length=19),
                existing_nullable=False,
            )

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
    op.create_index("ix_patient_indent_alloc_invoice_line_item_id", ALLOCATIONS, ["invoice_line_item_id"])
    op.create_index("ix_patient_indent_alloc_created_by_id", ALLOCATIONS, ["created_by_id"])
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
    op.create_index("ix_patient_indent_return_created_by_id", RETURNS, ["created_by_id"])

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
    op.drop_index("ix_patient_indent_return_created_by_id", table_name=RETURNS)
    op.drop_index("ix_patient_indent_return_allocation", table_name=RETURNS)
    op.drop_table(RETURNS)
    op.drop_index("ix_patient_indent_alloc_created_by_id", table_name=ALLOCATIONS)
    op.drop_index("ix_patient_indent_alloc_invoice_line_item_id", table_name=ALLOCATIONS)
    op.drop_index("ix_patient_indent_alloc_item_batch", table_name=ALLOCATIONS)
    op.drop_table(ALLOCATIONS)
