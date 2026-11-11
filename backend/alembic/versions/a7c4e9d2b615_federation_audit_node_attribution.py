"""record authenticated federation node identity in tenant audit logs

Revision ID: a7c4e9d2b615
Revises: f9b7c3d1e205
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa


revision = "a7c4e9d2b615"
down_revision = "f9b7c3d1e205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FederatedNode is stored in the control-plane database while this audit
    # table is tenant-local. Store immutable scalar snapshots, not cross-DB FKs.
    op.add_column(
        "federation_transfer_logs",
        sa.Column("requesting_node_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "federation_transfer_logs",
        sa.Column("requesting_key_prefix", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_federation_transfer_logs_requesting_node_id",
        "federation_transfer_logs",
        ["requesting_node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_federation_transfer_logs_requesting_node_id",
        table_name="federation_transfer_logs",
    )
    op.drop_column("federation_transfer_logs", "requesting_key_prefix")
    op.drop_column("federation_transfer_logs", "requesting_node_id")
