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

    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION prevent_procurement_reconciliation_event_mutation()
            RETURNS trigger AS $
            BEGIN
                RAISE EXCEPTION 'Procurement reconciliation investigation events are append-only';
            END;
            $ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER trg_proc_recon_event_append_only
            BEFORE UPDATE OR DELETE ON procurement_reconciliation_exception_events
            FOR EACH ROW EXECUTE FUNCTION prevent_procurement_reconciliation_event_mutation()
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_proc_recon_event_append_only ON procurement_reconciliation_exception_events")
        op.execute("DROP FUNCTION IF EXISTS prevent_procurement_reconciliation_event_mutation()")
    op.drop_column("procurement_reconciliation_exceptions", "missed_refresh_count")
    op.drop_column("procurement_reconciliation_exceptions", "source_present")
