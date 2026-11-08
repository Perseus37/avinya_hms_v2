"""Create immutable monthly reconciliation governance snapshots.

Revision ID: f3a9c2d7e610
Revises: e2c7a9d4b610
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a9c2d7e610"
down_revision = "e2c7a9d4b610"
branch_labels = None
depends_on = None

TABLE = "procurement_reconciliation_governance_reports"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_month", sa.String(length=7), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], ondelete="RESTRICT",
                                name="fk_recon_governance_generated_by"),
        sa.UniqueConstraint("report_month", name="uq_recon_governance_report_month"),
        sa.CheckConstraint("schema_version >= 1", name="ck_recon_governance_schema_version"),
    )
    op.create_index("ix_recon_governance_generated_at", TABLE, ["generated_at"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_reconciliation_governance_report_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Monthly reconciliation governance reports are immutable';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable
            BEFORE UPDATE OR DELETE ON {TABLE}
            FOR EACH ROW EXECUTE FUNCTION prevent_reconciliation_governance_report_mutation();
        """)
    elif op.get_bind().dialect.name == "sqlite":
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable_update
            BEFORE UPDATE ON {TABLE}
            BEGIN SELECT RAISE(ABORT, 'Monthly reconciliation governance reports are immutable'); END;
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{TABLE}_immutable_delete
            BEFORE DELETE ON {TABLE}
            BEGIN SELECT RAISE(ABORT, 'Monthly reconciliation governance reports are immutable'); END;
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable ON {TABLE}")
        op.execute("DROP FUNCTION IF EXISTS prevent_reconciliation_governance_report_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_immutable_delete")
    op.drop_index("ix_recon_governance_generated_at", table_name=TABLE)
    op.drop_table(TABLE)
