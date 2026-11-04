"""Add supplier shipment tracking and overdue PO visibility."""
from alembic import op
import sqlalchemy as sa

revision = "e2c7a9d4f610"
down_revision = "d8a4c2f1b690"
branch_labels = None
depends_on = None

shipment_status = sa.Enum(
    "PLANNED", "DISPATCHED", "IN_TRANSIT", "DELAYED",
    "DELIVERY_CONFIRMED", "CANCELLED",
    name="poshipmentstatusenum",
)


def upgrade() -> None:
    shipment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "procurement_po_shipments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("carrier", sa.String(120), nullable=False),
        sa.Column("tracking_number", sa.String(120), nullable=True),
        sa.Column("expected_delivery_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", shipment_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["po_id"], ["procurement_purchase_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_po_shipment_po_status", "procurement_po_shipments", ["po_id", "status"])
    op.create_index("ix_po_shipment_expected_status", "procurement_po_shipments", ["expected_delivery_at", "status"])
    op.create_table(
        "procurement_po_shipment_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("status", shipment_status, nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["procurement_po_shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_po_shipment_event_shipment_time", "procurement_po_shipment_events", ["shipment_id", "event_at"])


def downgrade() -> None:
    op.drop_index("ix_po_shipment_event_shipment_time", table_name="procurement_po_shipment_events")
    op.drop_table("procurement_po_shipment_events")
    op.drop_index("ix_po_shipment_expected_status", table_name="procurement_po_shipments")
    op.drop_index("ix_po_shipment_po_status", table_name="procurement_po_shipments")
    op.drop_table("procurement_po_shipments")
    shipment_status.drop(op.get_bind(), checkfirst=True)
