"""Add audit history for supplier compliance policy changes."""
from alembic import op
import sqlalchemy as sa

revision = "d4a7c2e9f610"
down_revision = "c9f4a2d7e610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_supplier_compliance_policy_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_id", sa.Integer(), nullable=True),
        sa.Column("vendor_category", sa.String(40), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("previous_is_required", sa.Boolean(), nullable=True),
        sa.Column("new_is_required", sa.Boolean(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_email", sa.String(255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["procurement_supplier_compliance_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_supplier_compliance_policy_audit_policy_time",
        "procurement_supplier_compliance_policy_audits",
        ["policy_id", "changed_at"],
    )
    op.create_index(
        "ix_supplier_compliance_policy_audit_actor_time",
        "procurement_supplier_compliance_policy_audits",
        ["changed_by_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_compliance_policy_audit_actor_time",
        table_name="procurement_supplier_compliance_policy_audits",
    )
    op.drop_index(
        "ix_supplier_compliance_policy_audit_policy_time",
        table_name="procurement_supplier_compliance_policy_audits",
    )
    op.drop_table("procurement_supplier_compliance_policy_audits")
