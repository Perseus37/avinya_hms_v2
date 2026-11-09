"""Add recipient read state to reconciliation notification inbox.

Revision ID: e2c7a9d4b610
Revises: d1e7a9c4b620
"""
from alembic import op
import sqlalchemy as sa

revision = "e2c7a9d4b610"
down_revision = "d1e7a9c4b620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_reconciliation_notification_outbox",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_recon_outbox_recipient_read_created",
        "procurement_reconciliation_notification_outbox",
        ["recipient_user_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recon_outbox_recipient_read_created",
        table_name="procurement_reconciliation_notification_outbox",
    )
    op.drop_column("procurement_reconciliation_notification_outbox", "read_at")
