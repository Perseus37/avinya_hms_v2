"""Add versioned reconciliation SLA policy governance and case snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "h3b7d9e2a610"
down_revision = "g2a4d6e8f110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_key", sa.String(48), nullable=False, server_default="DEFAULT"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.Column("severity_targets_hours", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(1000), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_by_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_proc_recon_sla_policy_version_positive"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_proc_recon_sla_policy_status"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_proc_recon_sla_policy_effective_window"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("policy_key", "version", name="uq_proc_recon_sla_policy_version"),
    )
    op.create_index(
        "ix_proc_recon_sla_policy_effective",
        "procurement_reconciliation_sla_policies",
        ["status", "effective_from", "effective_to"],
    )
    op.create_index(
        "uq_proc_recon_sla_policy_single_open",
        "procurement_reconciliation_sla_policies",
        ["policy_key"],
        unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED' AND effective_to IS NULL"),
        sqlite_where=sa.text("status = 'PUBLISHED' AND effective_to IS NULL"),
    )
    op.create_table(
        "procurement_reconciliation_sla_policy_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["policy_id"], ["procurement_reconciliation_sla_policies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_proc_recon_sla_policy_event_time",
        "procurement_reconciliation_sla_policy_events",
        ["policy_id", "occurred_at"],
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("sla_policy_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("sla_target_hours", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_proc_recon_exception_sla_policy",
        "procurement_reconciliation_exceptions",
        "procurement_reconciliation_sla_policies",
        ["sla_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_proc_recon_exception_sla_target_positive",
        "procurement_reconciliation_exceptions",
        "sla_target_hours IS NULL OR sla_target_hours BETWEEN 1 AND 8760",
    )
    op.execute("""
        UPDATE procurement_reconciliation_exceptions
        SET sla_target_hours = CASE severity
            WHEN 'CRITICAL' THEN 4
            WHEN 'HIGH' THEN 24
            WHEN 'MEDIUM' THEN 72
            WHEN 'LOW' THEN 168
            ELSE 168
        END
        WHERE sla_target_hours IS NULL
    """)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION prevent_proc_recon_sla_policy_event_mutation()
            RETURNS trigger LANGUAGE plpgsql AS '
            BEGIN
                RAISE EXCEPTION ''Reconciliation SLA policy events are append-only'';
            END;';
        """)
        op.execute("""
            CREATE FUNCTION guard_published_proc_recon_sla_policy()
            RETURNS trigger LANGUAGE plpgsql AS '
            BEGIN
                IF OLD.status = ''PUBLISHED'' AND (
                    NEW.policy_key IS DISTINCT FROM OLD.policy_key OR
                    NEW.version IS DISTINCT FROM OLD.version OR
                    NEW.severity_targets_hours::text IS DISTINCT FROM OLD.severity_targets_hours::text OR
                    NEW.change_reason IS DISTINCT FROM OLD.change_reason OR
                    NEW.effective_from IS DISTINCT FROM OLD.effective_from OR
                    NEW.created_by_id IS DISTINCT FROM OLD.created_by_id OR
                    NEW.created_at IS DISTINCT FROM OLD.created_at OR
                    NEW.published_by_id IS DISTINCT FROM OLD.published_by_id OR
                    NEW.published_at IS DISTINCT FROM OLD.published_at
                ) THEN
                    RAISE EXCEPTION ''Published reconciliation SLA policy versions are immutable'';
                END IF;
                RETURN NEW;
            END;';
        """)
        op.execute("""
            CREATE TRIGGER trg_proc_recon_sla_policy_immutable
            BEFORE UPDATE ON procurement_reconciliation_sla_policies
            FOR EACH ROW EXECUTE FUNCTION guard_published_proc_recon_sla_policy();
        """)
        op.execute("""
            CREATE TRIGGER trg_proc_recon_sla_policy_event_append_only
            BEFORE UPDATE OR DELETE ON procurement_reconciliation_sla_policy_events
            FOR EACH ROW EXECUTE FUNCTION prevent_proc_recon_sla_policy_event_mutation();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_sla_policy_immutable ON procurement_reconciliation_sla_policies")
        op.execute("DROP FUNCTION IF EXISTS guard_published_proc_recon_sla_policy()")
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_sla_policy_event_append_only ON procurement_reconciliation_sla_policy_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_proc_recon_sla_policy_event_mutation()")
    op.drop_constraint("ck_proc_recon_exception_sla_target_positive", "procurement_reconciliation_exceptions", type_="check")
    op.drop_constraint("fk_proc_recon_exception_sla_policy", "procurement_reconciliation_exceptions", type_="foreignkey")
    op.drop_column("procurement_reconciliation_exceptions", "sla_target_hours")
    op.drop_column("procurement_reconciliation_exceptions", "sla_policy_id")
    op.drop_index("ix_proc_recon_sla_policy_event_time", table_name="procurement_reconciliation_sla_policy_events")
    op.drop_table("procurement_reconciliation_sla_policy_events")
    op.drop_index("uq_proc_recon_sla_policy_single_open", table_name="procurement_reconciliation_sla_policies")
    op.drop_index("ix_proc_recon_sla_policy_effective", table_name="procurement_reconciliation_sla_policies")
    op.drop_table("procurement_reconciliation_sla_policies")
