"""Add configurable mandatory supplier compliance policies."""
from alembic import op
import sqlalchemy as sa

revision = "c9f4a2d7e610"
down_revision = "b8e4c2d7a610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "procurement_supplier_compliance_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_category", sa.String(40), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "vendor_category IN ('PHARMACEUTICALS','SURGICAL_IMPLANTS','LAB_REAGENTS','EQUIPMENT_MAINTENANCE','GENERAL_SUPPLIES')",
            name="ck_supplier_compliance_policy_category",
        ),
        sa.CheckConstraint("length(document_type) BETWEEN 2 AND 40", name="ck_supplier_compliance_policy_document_type"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.UniqueConstraint("vendor_category", "document_type", name="uq_supplier_compliance_policy_scope"),
    )
    op.create_index(
        "ix_supplier_compliance_policy_category_required",
        "procurement_supplier_compliance_policies",
        ["vendor_category", "is_required"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_compliance_policy_category_required",
        table_name="procurement_supplier_compliance_policies",
    )
    op.drop_table("procurement_supplier_compliance_policies")
