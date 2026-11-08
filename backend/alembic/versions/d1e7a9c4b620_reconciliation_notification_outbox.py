"""Create durable in-app reconciliation notification outbox.

Revision ID: d1e7a9c4b620
Revises: c8f2a6d1e940
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e7a9c4b620"
down_revision = "c8f2a6d1e940"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_reconciliation_notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("investigation_id", sa.Integer(),
                  sa.ForeignKey("procurement_reconciliation_investigations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("policy_id", sa.Integer(),
                  sa.ForeignKey("procurement_reconciliation_escalation_policies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False, server_default="IN_APP"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_recon_notification_outbox_idempotency"),
        sa.CheckConstraint("event_type IN ('SLA_WARNING','SLA_BREACHED')", name="ck_recon_outbox_event"),
        sa.CheckConstraint("channel = 'IN_APP'", name="ck_recon_outbox_channel"),
        sa.CheckConstraint("status = 'PENDING'", name="ck_recon_outbox_status"),
    )
    op.create_index("ix_recon_outbox_recipient_created",
                    "procurement_reconciliation_notification_outbox",
                    ["recipient_user_id", "created_at"])
    op.create_index("ix_recon_outbox_investigation",
                    "procurement_reconciliation_notification_outbox", ["investigation_id"])
    op.create_index("ix_recon_outbox_policy",
                    "procurement_reconciliation_notification_outbox", ["policy_id"])


def downgrade() -> None:
    op.drop_index("ix_recon_outbox_policy", table_name="procurement_reconciliation_notification_outbox")
    op.drop_index("ix_recon_outbox_investigation", table_name="procurement_reconciliation_notification_outbox")
    op.drop_index("ix_recon_outbox_recipient_created", table_name="procurement_reconciliation_notification_outbox")
    op.drop_table("procurement_reconciliation_notification_outbox")
