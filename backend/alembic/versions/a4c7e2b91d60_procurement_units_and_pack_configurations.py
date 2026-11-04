"""Add canonical procurement units and medication pack conversions."""

from alembic import op
import sqlalchemy as sa

revision = "a4c7e2b91d60"
down_revision = "3f8a2c6d1e90"
branch_labels = None
depends_on = None

units = [
    {"code": "TAB", "display_name": "Tablet", "dimension": "COUNT", "allows_fractional": False},
    {"code": "CAP", "display_name": "Capsule", "dimension": "COUNT", "allows_fractional": False},
    {"code": "STRIP", "display_name": "Strip", "dimension": "COUNT", "allows_fractional": False},
    {"code": "BOX", "display_name": "Box", "dimension": "COUNT", "allows_fractional": False},
    {"code": "VIAL", "display_name": "Vial", "dimension": "COUNT", "allows_fractional": False},
    {"code": "AMP", "display_name": "Ampoule", "dimension": "COUNT", "allows_fractional": False},
    {"code": "BOTTLE", "display_name": "Bottle", "dimension": "COUNT", "allows_fractional": False},
    {"code": "SACHET", "display_name": "Sachet", "dimension": "COUNT", "allows_fractional": False},
    {"code": "TUBE", "display_name": "Tube", "dimension": "COUNT", "allows_fractional": False},
    {"code": "PIECE", "display_name": "Piece", "dimension": "COUNT", "allows_fractional": False},
    {"code": "PACK", "display_name": "Pack", "dimension": "COUNT", "allows_fractional": False},
    {"code": "DOSE", "display_name": "Dose", "dimension": "COUNT", "allows_fractional": False},
    {"code": "PAIR", "display_name": "Pair", "dimension": "COUNT", "allows_fractional": False},
    {"code": "ML", "display_name": "Millilitre", "dimension": "VOLUME", "allows_fractional": True},
    {"code": "L", "display_name": "Litre", "dimension": "VOLUME", "allows_fractional": True},
    {"code": "MG", "display_name": "Milligram", "dimension": "MASS", "allows_fractional": True},
    {"code": "G", "display_name": "Gram", "dimension": "MASS", "allows_fractional": True},
    {"code": "KG", "display_name": "Kilogram", "dimension": "MASS", "allows_fractional": True},
]

def upgrade() -> None:
    op.create_table(
        "procurement_units_of_measure",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("dimension", sa.String(length=16), nullable=False),
        sa.Column("allows_fractional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("dimension IN ('COUNT', 'MASS', 'VOLUME', 'LENGTH')", name="ck_proc_uom_dimension"),
        sa.UniqueConstraint("code", name="uq_procurement_units_of_measure_code"),
    )
    unit_table = sa.table(
        "procurement_units_of_measure",
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("dimension", sa.String()),
        sa.column("allows_fractional", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(unit_table, [dict(unit, is_active=True) for unit in units])

    op.create_table(
        "procurement_medication_pack_configurations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medication_id", sa.Integer(), nullable=False),
        sa.Column("purchase_uom_id", sa.Integer(), nullable=False),
        sa.Column("base_uom_id", sa.Integer(), nullable=False),
        sa.Column("units_per_purchase_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("units_per_purchase_unit > 0", name="ck_med_pack_conversion_positive"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_med_pack_effective_window"),
        sa.ForeignKeyConstraint(["medication_id"], ["medication_master.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_uom_id"], ["procurement_units_of_measure.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["base_uom_id"], ["procurement_units_of_measure.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("medication_id", "purchase_uom_id", "effective_from", name="uq_med_pack_effective_start"),
    )
    op.create_index("ix_med_pack_medication_active", "procurement_medication_pack_configurations", ["medication_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_med_pack_medication_active", table_name="procurement_medication_pack_configurations")
    op.drop_table("procurement_medication_pack_configurations")
    op.drop_table("procurement_units_of_measure")
