"""Add escalation governance, monthly reconciliation reports and export register."""
from alembic import op
import sqlalchemy as sa

revision = "j5d8c2a7f410"
down_revision = "h4c2e7a9d510"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_escalation_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_key", sa.String(48), nullable=False, server_default="DEFAULT"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.Column("response_targets_hours", sa.JSON(), nullable=False),
        sa.Column("escalation_levels", sa.JSON(), nullable=False),
        sa.Column("notification_preferences", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(1000), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_by_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_proc_recon_escalation_policy_version"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_proc_recon_escalation_policy_status"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_proc_recon_escalation_policy_window"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("policy_key", "version", name="uq_proc_recon_escalation_policy_version"),
    )
    op.create_index(
        "uq_proc_recon_escalation_policy_active",
        "procurement_reconciliation_escalation_policies", ["policy_key"], unique=True,
        postgresql_where=sa.text("status = 'PUBLISHED' AND effective_to IS NULL"),
        sqlite_where=sa.text("status = 'PUBLISHED' AND effective_to IS NULL"),
    )
    op.create_table(
        "procurement_reconciliation_governance_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("report_snapshot", sa.JSON(), nullable=False),
        sa.Column("generated_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("period_start", "period_end", name="uq_proc_recon_governance_period"),
        sa.CheckConstraint("period_end >= period_start", name="ck_proc_recon_governance_period"),
    )
    op.create_index("ix_proc_recon_governance_report_created",
                    "procurement_reconciliation_governance_reports", ["created_at"])
    op.create_table(
        "procurement_reconciliation_audit_exports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("exception_id", sa.Integer(), nullable=True),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="GENERATED"),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("filter_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["exception_id"], ["procurement_reconciliation_exceptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('GENERATED','FAILED','EXPIRED')", name="ck_proc_recon_audit_export_status"),
        sa.CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="ck_proc_recon_audit_export_size"),
    )
    op.create_index("ix_proc_recon_audit_export_time",
                    "procurement_reconciliation_audit_exports", ["requested_at"])
    op.create_index("ix_proc_recon_audit_export_actor",
                    "procurement_reconciliation_audit_exports", ["actor_user_id", "requested_at"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION prevent_proc_recon_governance_mutation()
            RETURNS trigger LANGUAGE plpgsql AS '
            BEGIN
                RAISE EXCEPTION ''Reconciliation governance snapshots and export records are immutable'';
            END;';
        """)
        for table, trigger in [
            ("procurement_reconciliation_governance_reports", "trg_proc_recon_governance_report_immutable"),
            ("procurement_reconciliation_audit_exports", "trg_proc_recon_audit_export_immutable"),
        ]:
            op.execute(f"""
                CREATE TRIGGER {trigger}
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_proc_recon_governance_mutation();
            """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_audit_export_immutable ON procurement_reconciliation_audit_exports")
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_governance_report_immutable ON procurement_reconciliation_governance_reports")
        op.execute("DROP FUNCTION IF EXISTS prevent_proc_recon_governance_mutation()")
    op.drop_index("ix_proc_recon_audit_export_actor", table_name="procurement_reconciliation_audit_exports")
    op.drop_index("ix_proc_recon_audit_export_time", table_name="procurement_reconciliation_audit_exports")
    op.drop_table("procurement_reconciliation_audit_exports")
    op.drop_index("ix_proc_recon_governance_report_created", table_name="procurement_reconciliation_governance_reports")
    op.drop_table("procurement_reconciliation_governance_reports")
    op.drop_index("uq_proc_recon_escalation_policy_active", table_name="procurement_reconciliation_escalation_policies")
    op.drop_table("procurement_reconciliation_escalation_policies")
