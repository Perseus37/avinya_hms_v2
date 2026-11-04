"""Use precise decimal paise valuation for inventory base units."""

from alembic import op
import sqlalchemy as sa

revision = "c8f2a6d1e940"
down_revision = "b6d3a9e1f420"
branch_labels = None
depends_on = None

TABLES = ("inventory_batches", "inventory_movements", "inventory_transfers")

def upgrade() -> None:
    op.add_column("inventory_batches", sa.Column("base_uom_code", sa.String(length=24), nullable=True))
    op.add_column("inventory_movements", sa.Column("base_uom_code", sa.String(length=24), nullable=True))
    op.add_column("inventory_transfers", sa.Column("base_uom_code", sa.String(length=24), nullable=True))
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "unit_price_paise",
                existing_type=sa.Integer(),
                type_=sa.Numeric(24, 8),
                existing_nullable=False,
            )


def downgrade() -> None:
    # A decimal base-unit price may contain fractional paise; downgrade would lose precision.
    # Refuse an unsafe lossy rollback instead of silently rounding inventory valuation.
    bind = op.get_bind()
    for table in TABLES:
        fractional = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} WHERE unit_price_paise != CAST(unit_price_paise AS INTEGER)"
        )).scalar_one()
        if fractional:
            raise RuntimeError(
                f"Cannot downgrade {table}: fractional-paise inventory valuations exist."
            )
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "unit_price_paise",
                existing_type=sa.Numeric(24, 8),
                type_=sa.Integer(),
                existing_nullable=False,
            )
    op.drop_column("inventory_transfers", "base_uom_code")
    op.drop_column("inventory_movements", "base_uom_code")
    op.drop_column("inventory_batches", "base_uom_code")
