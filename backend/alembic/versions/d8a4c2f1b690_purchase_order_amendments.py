"""Add immutable purchase-order amendment snapshots and review lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "d8a4c2f1b690"
down_revision = "c6d9a2e4f710"
branch_labels = None
depends_on = None

amendment_status = sa.Enum("PENDING", "APPROVED", "REJECTED", name="poamendmentstatusenum")


def upgrade() -> None:
    amendment_status.create(op.get_bind(), checkfirst=True)
    op.add_column("procurement_purchase_orders", sa.Column("amendment_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "procurement_po_amendments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_snapshot", sa.JSON(), nullable=False),
        sa.Column("proposed_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", amendment_status, nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["po_id"], ["procurement_purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("po_id", "version", name="uq_po_amendment_version"),
    )
    op.create_index("ix_po_amendment_po_status", "procurement_po_amendments", ["po_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_po_amendment_po_status", table_name="procurement_po_amendments")
    op.drop_table("procurement_po_amendments")
    op.drop_column("procurement_purchase_orders", "amendment_version")
    amendment_status.drop(op.get_bind(), checkfirst=True)
