"""Track source presence for reconciliation exceptions."""
from alembic import op
import sqlalchemy as sa

revision = "e4b8c2d7a610"
down_revision = "d7a4c2e9f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("source_present", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "procurement_reconciliation_exceptions",
        sa.Column("missed_refresh_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("procurement_reconciliation_exceptions", "missed_refresh_count")
    op.drop_column("procurement_reconciliation_exceptions", "source_present")
