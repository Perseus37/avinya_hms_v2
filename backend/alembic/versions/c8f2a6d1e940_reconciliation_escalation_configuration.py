"""Add escalation policy and notification preference configuration.

Revision ID: c8f2a6d1e940
Revises: e7b4c2d9a610
"""
from alembic import op
import sqlalchemy as sa

revision = "c8f2a6d1e940"
down_revision = "e7b4c2d9a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_escalation_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("trigger", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recipient_role_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("channels", sa.Text(), nullable=False, server_default='["IN_APP"]'),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("severity", "trigger", "version", name="uq_recon_escalation_version"),
        sa.CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_escalation_severity"),
        sa.CheckConstraint("trigger IN ('WARNING','BREACHED')", name="ck_recon_escalation_trigger"),
        sa.CheckConstraint("version >= 1", name="ck_recon_escalation_version_positive"),
        sa.CheckConstraint("delay_minutes >= 0", name="ck_recon_escalation_delay_nonneg"),
    )
    op.create_index(
        "uq_recon_escalation_active",
        "procurement_reconciliation_escalation_policies",
        ["severity", "trigger"], unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_table(
        "procurement_reconciliation_notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("user_id", "event_type", "channel", name="uq_recon_notification_preference"),
        sa.CheckConstraint("event_type IN ('SLA_WARNING','SLA_BREACHED')", name="ck_recon_notification_event"),
        sa.CheckConstraint("channel IN ('IN_APP','EMAIL','SMS','PUSH')", name="ck_recon_notification_channel"),
    )
    op.create_table(
        "procurement_reconciliation_notification_config_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recon_escalation_created_by",
                    "procurement_reconciliation_escalation_policies", ["created_by_id"])
    op.create_index("ix_recon_notification_pref_updated_by",
                    "procurement_reconciliation_notification_preferences", ["updated_by_id"])
    op.create_index("ix_recon_notification_config_actor_time",
                    "procurement_reconciliation_notification_config_events",
                    ["actor_user_id", "occurred_at"])
    op.create_index("ix_recon_notification_config_subject",
                    "procurement_reconciliation_notification_config_events", ["subject_user_id"])
    # Protect audit evidence at the database boundary on PostgreSQL and SQLite.
    table = "procurement_reconciliation_notification_config_events"
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text(f"""
            CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table}
            BEGIN SELECT RAISE(ABORT, 'Notification configuration audit is append-only'); END
        """))
        op.execute(sa.text(f"""
            CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT, 'Notification configuration audit is append-only'); END
        """))
    else:
        op.execute(f"""
            CREATE OR REPLACE FUNCTION prevent_{table}_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Notification configuration audit is append-only';
            END;
            $ LANGUAGE plpgsql
        """)
        op.execute(sa.text(f"""
            CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_{table}_mutation()
        """))


def downgrade() -> None:
    op.drop_index("ix_recon_notification_config_subject", table_name="procurement_reconciliation_notification_config_events")
    op.drop_index("ix_recon_notification_config_actor_time",
                  table_name="procurement_reconciliation_notification_config_events")
    op.drop_index("ix_recon_notification_pref_updated_by", table_name="procurement_reconciliation_notification_preferences")
    op.drop_index("ix_recon_escalation_created_by", table_name="procurement_reconciliation_escalation_policies")
    if op.get_bind().dialect.name == "sqlite":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_procurement_reconciliation_notification_config_events_immutable_update"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_procurement_reconciliation_notification_config_events_immutable_delete"))
    else:
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_procurement_reconciliation_notification_config_events_immutable ON procurement_reconciliation_notification_config_events"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS prevent_procurement_reconciliation_notification_config_events_mutation()"))
    op.drop_table("procurement_reconciliation_notification_config_events")
    op.drop_table("procurement_reconciliation_notification_preferences")
    op.drop_index("uq_recon_escalation_active", table_name="procurement_reconciliation_escalation_policies")
    op.drop_table("procurement_reconciliation_escalation_policies")
