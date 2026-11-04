"""Add destination location and independent inspection audit to procurement GRNs."""

from alembic import op
import sqlalchemy as sa


revision = "7a91c4e2b630"
down_revision = "8b6d2f4a9c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "procurement_grn",
        sa.Column("location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_procurement_grn_location_id_pharmacy_locations",
        "procurement_grn",
        "pharmacy_locations",
        ["location_id"],
        ["id"],
    )
    op.create_index(
        "ix_procurement_grn_location_id",
        "procurement_grn",
        ["location_id"],
        unique=False,
    )
    op.add_column(
        "procurement_grn",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "procurement_grn",
        "inspected_by_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "procurement_grn",
        "inspected_by_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("procurement_grn", "accepted_at")
    op.drop_index("ix_procurement_grn_location_id", table_name="procurement_grn")
    op.drop_constraint(
        "fk_procurement_grn_location_id_pharmacy_locations",
        "procurement_grn",
        type_="foreignkey",
    )
    op.drop_column("procurement_grn", "location_id")
