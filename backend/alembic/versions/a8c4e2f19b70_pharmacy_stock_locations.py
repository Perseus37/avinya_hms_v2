"""Add branch-local pharmacy stock locations and backfill existing batches."""

from alembic import op
import sqlalchemy as sa

revision = "a8c4e2f19b70"
down_revision = "f9b7c3d1e205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_locations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location_type", sa.String(length=30), server_default="STORE", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", name="uq_pharmacy_locations_code"),
    )
    op.execute(
        "INSERT INTO pharmacy_locations (code, name, location_type, is_active) "
        "VALUES ('MAIN', 'Main Pharmacy Store', 'STORE', true)"
    )
    op.add_column("inventory_batches", sa.Column("location_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE inventory_batches SET location_id = "
        "(SELECT id FROM pharmacy_locations WHERE code = 'MAIN')"
    )
    op.alter_column("inventory_batches", "location_id", nullable=False)
    op.create_foreign_key(
        "fk_inventory_batches_location_id_pharmacy_locations",
        "inventory_batches", "pharmacy_locations", ["location_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_inventory_batches_location_id", "inventory_batches", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_batches_location_id", table_name="inventory_batches")
    op.drop_constraint("fk_inventory_batches_location_id_pharmacy_locations", "inventory_batches", type_="foreignkey")
    op.drop_column("inventory_batches", "location_id")
    op.drop_table("pharmacy_locations")
