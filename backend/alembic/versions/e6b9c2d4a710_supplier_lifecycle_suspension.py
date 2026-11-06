"""Add maker-checker supplier suspension and reinstatement lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "e6b9c2d4a710"
down_revision = "d4a7c2e9f610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("procurement_vendors", sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("procurement_vendors", sa.Column("suspension_reason", sa.Text(), nullable=True))
    op.add_column("procurement_vendors", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("procurement_vendors", sa.Column("suspended_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_procurement_vendors_suspended_by_id_users",
        "procurement_vendors", "users", ["suspended_by_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_procurement_vendors_is_suspended", "procurement_vendors", ["is_suspended"])
    op.create_table(
        "procurement_supplier_lifecycle_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.CheckConstraint("action IN ('SUSPEND','REINSTATE')", name="ck_supplier_lifecycle_action"),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_supplier_lifecycle_status"),
        sa.ForeignKeyConstraint(["vendor_id"], ["procurement_vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_supplier_lifecycle_vendor_created", "procurement_supplier_lifecycle_requests", ["vendor_id", "requested_at"])
    op.create_index("ix_supplier_lifecycle_status_created", "procurement_supplier_lifecycle_requests", ["status", "requested_at"])


def downgrade() -> None:
    op.drop_index("ix_supplier_lifecycle_status_created", table_name="procurement_supplier_lifecycle_requests")
    op.drop_index("ix_supplier_lifecycle_vendor_created", table_name="procurement_supplier_lifecycle_requests")
    op.drop_table("procurement_supplier_lifecycle_requests")
    op.drop_index("ix_procurement_vendors_is_suspended", table_name="procurement_vendors")
    op.drop_constraint("fk_procurement_vendors_suspended_by_id_users", "procurement_vendors", type_="foreignkey")
    op.drop_column("procurement_vendors", "suspended_by_id")
    op.drop_column("procurement_vendors", "suspended_at")
    op.drop_column("procurement_vendors", "suspension_reason")
    op.drop_column("procurement_vendors", "is_suspended")
