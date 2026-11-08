"""Add durable reconciliation investigation lifecycle and immutable events.

Revision ID: b8d3f6a1c920
Revises: a7c4e9d2f610
"""
from alembic import op
import sqlalchemy as sa

revision = "b8d3f6a1c920"
down_revision = "a7c4e9d2f610"
branch_labels = None
depends_on = None

EVENT_TABLE = "procurement_reconciliation_investigation_events"


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_investigations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_key", sa.String(220), nullable=False),
        sa.Column("candidate_type", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("opened_by_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.String(120), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_investigation_severity"),
        sa.CheckConstraint("status IN ('OPEN','ASSIGNED','IN_REVIEW','RESOLVED','DISMISSED')", name="ck_recon_investigation_status"),
        sa.CheckConstraint("version >= 1", name="ck_recon_investigation_version_positive"),
        sa.UniqueConstraint("external_key", name="uq_recon_investigation_external_key"),
        sa.ForeignKeyConstraint(["opened_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_recon_investigation_status_severity", "procurement_reconciliation_investigations", ["status", "severity"])
    op.create_index("ix_recon_investigation_assignee_status", "procurement_reconciliation_investigations", ["assigned_to_id", "status"])
    op.create_index("ix_recon_investigation_source", "procurement_reconciliation_investigations", ["source_type", "source_id"])

    op.create_table(
        EVENT_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["procurement_reconciliation_investigations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_recon_investigation_event_case_time", EVENT_TABLE, ["investigation_id", "occurred_at"])
    op.create_index("ix_recon_investigation_event_actor_time", EVENT_TABLE, ["actor_user_id", "occurred_at"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_reconciliation_investigation_event_mutation()
            RETURNS trigger AS $fn$
            BEGIN
                RAISE EXCEPTION 'Reconciliation investigation events are append-only';
            END;
            $fn$ LANGUAGE plpgsql
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{EVENT_TABLE}_immutable
            BEFORE UPDATE OR DELETE ON {EVENT_TABLE}
            FOR EACH ROW EXECUTE FUNCTION prevent_reconciliation_investigation_event_mutation()
        """)
    elif bind.dialect.name == "sqlite":
        op.execute(f"""
            CREATE TRIGGER trg_{EVENT_TABLE}_immutable_update
            BEFORE UPDATE ON {EVENT_TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Reconciliation investigation events are append-only');
            END
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{EVENT_TABLE}_immutable_delete
            BEFORE DELETE ON {EVENT_TABLE}
            BEGIN
                SELECT RAISE(ABORT, 'Reconciliation investigation events are append-only');
            END
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{EVENT_TABLE}_immutable ON {EVENT_TABLE}")
        op.execute("DROP FUNCTION IF EXISTS prevent_reconciliation_investigation_event_mutation()")
    elif bind.dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{EVENT_TABLE}_immutable_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{EVENT_TABLE}_immutable_delete")
    op.drop_index("ix_recon_investigation_event_actor_time", table_name=EVENT_TABLE)
    op.drop_index("ix_recon_investigation_event_case_time", table_name=EVENT_TABLE)
    op.drop_table(EVENT_TABLE)
    op.drop_index("ix_recon_investigation_source", table_name="procurement_reconciliation_investigations")
    op.drop_index("ix_recon_investigation_assignee_status", table_name="procurement_reconciliation_investigations")
    op.drop_index("ix_recon_investigation_status_severity", table_name="procurement_reconciliation_investigations")
    op.drop_table("procurement_reconciliation_investigations")
