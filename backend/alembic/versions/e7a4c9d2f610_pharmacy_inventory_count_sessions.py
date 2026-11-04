"""Add blind physical inventory count sessions and count lines."""

from alembic import op
import sqlalchemy as sa

revision = "e7a4c9d2f610"
down_revision = "d4e9a7b2c613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_count_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("pharmacy_locations.id"), nullable=False),
        sa.Column("count_type", sa.String(length=20), server_default="CYCLE", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("count_type IN ('CYCLE', 'FULL', 'SPOT')", name="ck_inventory_count_type"),
    )
    op.create_index("ix_inventory_count_sessions_location_id", "inventory_count_sessions", ["location_id"])
    op.create_index("ix_inventory_count_location_status", "inventory_count_sessions", ["location_id", "status"])

    op.create_table(
        "inventory_count_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("inventory_count_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id"), nullable=False),
        sa.Column("medication_id", sa.Integer(), sa.ForeignKey("medication_master.id"), nullable=False),
        sa.Column("batch_number", sa.String(length=50), nullable=False),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_quantity", sa.Integer(), nullable=False),
        sa.Column("snapshot_movement_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("physical_quantity", sa.Integer(), nullable=True),
        sa.Column("counted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recount_quantity", sa.Integer(), nullable=True),
        sa.Column("recounted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason_code", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("session_id", "inventory_batch_id", name="uq_inventory_count_session_batch"),
        sa.CheckConstraint("snapshot_quantity >= 0", name="ck_inventory_count_snapshot_nonnegative"),
        sa.CheckConstraint("physical_quantity IS NULL OR physical_quantity >= 0", name="ck_inventory_count_physical_nonnegative"),
    )
    op.create_index("ix_inventory_count_lines_session_id", "inventory_count_lines", ["session_id"])
    op.create_index("ix_inventory_count_lines_batch", "inventory_count_lines", ["inventory_batch_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_count_lines_batch", table_name="inventory_count_lines")
    op.drop_index("ix_inventory_count_lines_session_id", table_name="inventory_count_lines")
    op.drop_table("inventory_count_lines")
    op.drop_index("ix_inventory_count_location_status", table_name="inventory_count_sessions")
    op.drop_index("ix_inventory_count_sessions_location_id", table_name="inventory_count_sessions")
    op.drop_table("inventory_count_sessions")
