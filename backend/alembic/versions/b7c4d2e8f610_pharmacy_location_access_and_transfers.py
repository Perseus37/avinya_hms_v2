"""Add pharmacy location grants and audited stock transfer workflow."""

from alembic import op
import sqlalchemy as sa

revision = "b7c4d2e8f610"
down_revision = "a8c4e2f19b70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_location_access",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("pharmacy_locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("location_id", "user_id", name="uq_pharmacy_location_user"),
    )
    op.create_index("ix_pharmacy_location_access_location_id", "pharmacy_location_access", ["location_id"])
    op.create_index("ix_pharmacy_location_access_user_id", "pharmacy_location_access", ["user_id"])

    op.execute(
        """
        INSERT INTO permissions (code, description, module)
        SELECT 'pharmacy:location:manage',
               'Assign and revoke staff access to pharmacy locations',
               'Pharmacy'
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions WHERE code = 'pharmacy:location:manage'
        )
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.code = 'pharmacy:location:manage'
        WHERE r.code = 'ROLE_ADMIN'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )

    # Preserve access for existing pharmacy staff when moving from branch-wide to location-scoped access.
    op.execute(
        """
        INSERT INTO pharmacy_location_access (location_id, user_id, is_active)
        SELECT pl.id, ur.user_id, true
        FROM pharmacy_locations pl
        JOIN user_roles ur ON (
            ur.department_id IN (
                SELECT d.id FROM departments d WHERE d.code IN ('PHARMACY', 'DEPT_PHARMACY')
            )
            OR ur.role_id IN (
                SELECT r.id FROM roles r
                WHERE r.code IN ('ROLE_PHARMACIST', 'ROLE_PHARMACY_MANAGER', 'PHARMACIST')
            )
        )
        WHERE pl.code = 'MAIN'
        GROUP BY pl.id, ur.user_id
        """
    )

    op.drop_constraint("uq_med_batch_number", "inventory_batches", type_="unique")
    op.create_unique_constraint(
        "uq_med_batch_location_batch",
        "inventory_batches",
        ["medication_id", "batch_number", "location_id"],
    )

    op.create_table(
        "inventory_transfers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id"), nullable=False),
        sa.Column("source_location_id", sa.Integer(), sa.ForeignKey("pharmacy_locations.id"), nullable=False),
        sa.Column("destination_location_id", sa.Integer(), sa.ForeignKey("pharmacy_locations.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="REQUESTED", nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dispatched_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_transfer_qty_pos"),
        sa.CheckConstraint("source_location_id != destination_location_id", name="ck_inventory_transfer_distinct_locations"),
    )
    op.create_index("ix_inventory_transfers_source_batch_id", "inventory_transfers", ["source_batch_id"])
    op.create_index("ix_inventory_transfers_status_created", "inventory_transfers", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_inventory_transfers_status_created", table_name="inventory_transfers")
    op.drop_index("ix_inventory_transfers_source_batch_id", table_name="inventory_transfers")
    op.drop_table("inventory_transfers")
    op.drop_constraint("uq_med_batch_location_batch", "inventory_batches", type_="unique")
    op.create_unique_constraint(
        "uq_med_batch_number",
        "inventory_batches",
        ["medication_id", "batch_number"],
    )
    op.drop_index("ix_pharmacy_location_access_user_id", table_name="pharmacy_location_access")
    op.drop_index("ix_pharmacy_location_access_location_id", table_name="pharmacy_location_access")
    op.drop_table("pharmacy_location_access")
