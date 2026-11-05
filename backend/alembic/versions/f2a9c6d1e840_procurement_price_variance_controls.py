"""Add medication purchase-price controls and PO variance review evidence."""

from alembic import op
import sqlalchemy as sa

revision = "f2a9c6d1e840"
down_revision = "c8f2a6d1e940"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_medication_price_controls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medication_id", sa.Integer(), nullable=False),
        sa.Column("max_variance_pct", sa.Integer(), nullable=False),
        sa.Column("minimum_observations", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lookback_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("max_variance_pct >= 0 AND max_variance_pct <= 1000", name="ck_med_price_control_variance_range"),
        sa.CheckConstraint("minimum_observations >= 2 AND minimum_observations <= 100", name="ck_med_price_control_min_observations"),
        sa.CheckConstraint("lookback_days >= 1 AND lookback_days <= 1825", name="ck_med_price_control_lookback_days"),
        sa.ForeignKeyConstraint(["medication_id"], ["medication_master.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("medication_id", name="uq_proc_medication_price_control"),
    )
    op.create_table(
        "procurement_po_price_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("po_item_id", sa.Integer(), nullable=False),
        sa.Column("medication_id", sa.Integer(), nullable=False),
        sa.Column("base_uom_code", sa.String(length=24), nullable=False),
        sa.Column("proposed_base_unit_price_paise", sa.Numeric(24, 8), nullable=False),
        sa.Column("benchmark_median_paise", sa.Numeric(24, 8), nullable=False),
        sa.Column("benchmark_min_paise", sa.Numeric(24, 8), nullable=False),
        sa.Column("benchmark_max_paise", sa.Numeric(24, 8), nullable=False),
        sa.Column("benchmark_observations", sa.Integer(), nullable=False),
        sa.Column("threshold_pct", sa.Integer(), nullable=False),
        sa.Column("variance_pct", sa.Numeric(12, 4), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("benchmark_observations >= 0", name="ck_po_price_review_observations_non_neg"),
        sa.CheckConstraint("threshold_pct >= 0", name="ck_po_price_review_threshold_non_neg"),
        sa.ForeignKeyConstraint(["po_id"], ["procurement_purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_item_id"], ["procurement_po_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["medication_id"], ["medication_master.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.UniqueConstraint("po_id", "po_item_id", name="uq_po_price_review_line"),
    )
    op.create_index("ix_procurement_po_price_reviews_po_id", "procurement_po_price_reviews", ["po_id"])


def downgrade() -> None:
    op.drop_index("ix_procurement_po_price_reviews_po_id", table_name="procurement_po_price_reviews")
    op.drop_table("procurement_po_price_reviews")
    op.drop_table("procurement_medication_price_controls")
