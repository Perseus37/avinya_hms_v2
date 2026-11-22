"""Add immutable pharmacy inventory stock adjustment history.

Revision ID: a8f4c2d9e610
Revises: f3b8a1d6c902, 3e7a1c9d5b42
Create Date: 2026-11-15
"""

from alembic import op
import sqlalchemy as sa


revision = "a8f4c2d9e610"
down_revision = ("f3b8a1d6c902", "3e7a1c9d5b42")
branch_labels = None
depends_on = None


TABLE = "inventory_stock_adjustment_logs"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("quantity_adjustment", sa.Integer(), nullable=False),
        sa.Column("quantity_before", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity_adjustment <> 0", name="ck_inv_adjustment_nonzero"),
        sa.CheckConstraint("quantity_before >= 0", name="ck_inv_adjustment_before_nonneg"),
        sa.CheckConstraint("quantity_after >= 0", name="ck_inv_adjustment_after_nonneg"),
        sa.CheckConstraint(
            "quantity_after = quantity_before + quantity_adjustment",
            name="ck_inv_adjustment_balance_consistent",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["inventory_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_inv_adjustment_batch_created", TABLE, ["batch_id", "created_at"])
    op.create_index("ix_inv_adjustment_actor_id", TABLE, ["actor_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"""
            CREATE OR REPLACE FUNCTION prevent_{TABLE}_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Pharmacy stock adjustment history is immutable';
            END;
            $$;
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable
            BEFORE UPDATE OR DELETE ON {TABLE}
            FOR EACH ROW EXECUTE FUNCTION prevent_{TABLE}_mutation();
        """)
    elif op.get_bind().dialect.name == "sqlite":
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable_update
            BEFORE UPDATE ON {TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Pharmacy stock adjustment history is immutable');
            END;
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable_delete
            BEFORE DELETE ON {TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Pharmacy stock adjustment history is immutable');
            END;
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable ON {TABLE}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{TABLE}_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable_delete")
    op.drop_index("ix_inv_adjustment_actor_id", table_name=TABLE)
    op.drop_index("ix_inv_adjustment_batch_created", table_name=TABLE)
    op.drop_table(TABLE)
