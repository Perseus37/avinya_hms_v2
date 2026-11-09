"""Add versioned reconciliation SLA policies and case snapshots.

Revision ID: e7b4c2d9a610
Revises: d6a9c2f4e810
"""
from alembic import op
import sqlalchemy as sa

revision = "e7b4c2d9a610"
down_revision = "d6a9c2f4e810"
branch_labels = None
depends_on = None

CASE_TABLE = "procurement_reconciliation_investigations"
POLICY_TABLE = "procurement_reconciliation_sla_policies"


def upgrade() -> None:
    op.create_table(
        POLICY_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("target_minutes", sa.Integer(), nullable=False),
        sa.Column("warning_percent", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("severity", "version", name="uq_recon_sla_severity_version"),
        sa.CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_sla_severity"),
        sa.CheckConstraint("target_minutes > 0", name="ck_recon_sla_target_positive"),
        sa.CheckConstraint("warning_percent BETWEEN 1 AND 99", name="ck_recon_sla_warning_percent"),
        sa.CheckConstraint("version >= 1", name="ck_recon_sla_version_positive"),
    )
    op.create_index("ix_recon_sla_created_by", POLICY_TABLE, ["created_by_id"])
    op.create_index(
        "uq_recon_sla_active_severity", POLICY_TABLE, ["severity"], unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )
    with op.batch_alter_table(CASE_TABLE) as batch:
        batch.add_column(sa.Column("sla_policy_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sla_policy_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sla_target_minutes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sla_warning_percent", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sla_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_recon_investigation_sla_policy", POLICY_TABLE,
            ["sla_policy_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_recon_investigation_sla_snapshot",
            "(sla_policy_id IS NULL AND sla_policy_version IS NULL AND sla_target_minutes IS NULL AND sla_warning_percent IS NULL AND sla_started_at IS NULL AND sla_due_at IS NULL) OR "
            "(sla_policy_id IS NOT NULL AND sla_policy_version >= 1 AND sla_target_minutes > 0 AND sla_warning_percent BETWEEN 1 AND 99 AND sla_started_at IS NOT NULL AND sla_due_at IS NOT NULL)",
        )
    op.create_index("ix_recon_investigation_sla_due_status", CASE_TABLE, ["status", "sla_due_at"])
    op.create_index("ix_recon_investigation_sla_policy", CASE_TABLE, ["sla_policy_id"])


def downgrade() -> None:
    op.drop_index("ix_recon_investigation_sla_policy", table_name=CASE_TABLE)
    op.drop_index("ix_recon_investigation_sla_due_status", table_name=CASE_TABLE)
    with op.batch_alter_table(CASE_TABLE) as batch:
        batch.drop_constraint("ck_recon_investigation_sla_snapshot", type_="check")
        batch.drop_constraint("fk_recon_investigation_sla_policy", type_="foreignkey")
        batch.drop_column("sla_due_at")
        batch.drop_column("sla_started_at")
        batch.drop_column("sla_warning_percent")
        batch.drop_column("sla_target_minutes")
        batch.drop_column("sla_policy_version")
        batch.drop_column("sla_policy_id")
    op.drop_index("uq_recon_sla_active_severity", table_name=POLICY_TABLE)
    op.drop_index("ix_recon_sla_created_by", table_name=POLICY_TABLE)
    op.drop_table(POLICY_TABLE)
