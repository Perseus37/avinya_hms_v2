"""add short-lived server-side federation discovery receipts

Revision ID: 6c9f2a1d8b40
Revises: 5b7c9e2d1a64
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c9f2a1d8b40"
down_revision: Union[str, None] = "5b7c9e2d1a64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "federated_discovery_receipts",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("calling_node_id", sa.Integer(), nullable=False),
        sa.Column("destination_branch_code", sa.String(length=50), nullable=False),
        sa.Column("selector_type", sa.String(length=8), nullable=False),
        sa.Column("selector_hash", sa.String(length=64), nullable=False),
        sa.Column("pointer_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("source_pointer_id", sa.Integer(), nullable=False),
        sa.Column("source_branch_code", sa.String(length=50), nullable=False),
        sa.Column("source_mrn", sa.String(length=50), nullable=False),
        sa.Column("summary_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["calling_node_id"],
            ["federated_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_pointer_id"],
            ["global_patient_pointers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_federated_discovery_receipts_calling_node_id",
        "federated_discovery_receipts",
        ["calling_node_id"],
    )
    op.create_index(
        "ix_federated_discovery_receipts_destination_branch_code",
        "federated_discovery_receipts",
        ["destination_branch_code"],
    )
    op.create_index(
        "ix_federated_discovery_receipts_expires_at",
        "federated_discovery_receipts",
        ["expires_at"],
    )
    op.create_index(
        "ix_federated_discovery_receipts_destination",
        "federated_discovery_receipts",
        ["destination_branch_code", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_federated_discovery_receipts_destination",
        table_name="federated_discovery_receipts",
    )
    op.drop_index(
        "ix_federated_discovery_receipts_expires_at",
        table_name="federated_discovery_receipts",
    )
    op.drop_index(
        "ix_federated_discovery_receipts_destination_branch_code",
        table_name="federated_discovery_receipts",
    )
    op.drop_index(
        "ix_federated_discovery_receipts_calling_node_id",
        table_name="federated_discovery_receipts",
    )
    op.drop_table("federated_discovery_receipts")
