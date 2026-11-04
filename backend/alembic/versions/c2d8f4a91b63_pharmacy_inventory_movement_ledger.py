"""Create append-only pharmacy inventory movement ledger."""

from alembic import op
import sqlalchemy as sa

revision = "c2d8f4a91b63"
down_revision = "b7c4d2e8f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("pharmacy_locations.id"), nullable=False),
        sa.Column("medication_id", sa.Integer(), sa.ForeignKey("medication_master.id"), nullable=False),
        sa.Column("inventory_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id"), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("stock_before", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=40), nullable=True),
        sa.Column("reference_id", sa.String(length=80), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("quantity_delta != 0", name="ck_inventory_movement_nonzero_delta"),
        sa.CheckConstraint("stock_before >= 0 AND stock_after >= 0", name="ck_inventory_movement_stock_nonnegative"),
        sa.CheckConstraint("stock_after = stock_before + quantity_delta", name="ck_inventory_movement_balance_delta"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_inventory_movement_unit_price_nonnegative"),
    )
    op.create_index("ix_inventory_movements_location_created", "inventory_movements", ["location_id", "created_at"])
    op.create_index("ix_inventory_movements_batch_created", "inventory_movements", ["inventory_batch_id", "created_at"])
    op.create_index("ix_inventory_movements_reference", "inventory_movements", ["reference_type", "reference_id"])

    # PostgreSQL enforces append-only behavior below the ORM layer as well.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE FUNCTION prevent_inventory_movement_mutation()
            RETURNS trigger AS $
            BEGIN
                RAISE EXCEPTION 'inventory_movements is append-only';
            END;
            $ LANGUAGE plpgsql
        """)
        op.execute("""
            CREATE TRIGGER trg_inventory_movements_append_only
            BEFORE UPDATE OR DELETE ON inventory_movements
            FOR EACH ROW EXECUTE FUNCTION prevent_inventory_movement_mutation()
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_inventory_movements_append_only ON inventory_movements")
        op.execute("DROP FUNCTION IF EXISTS prevent_inventory_movement_mutation()")
    op.drop_index("ix_inventory_movements_reference", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_batch_created", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_location_created", table_name="inventory_movements")
    op.drop_table("inventory_movements")
