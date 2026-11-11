"""add trusted corporate group identity to tenant registry

Revision ID: 5b7c9e2d1a64
Revises: 4d7e9b2c1a85
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5b7c9e2d1a64"
down_revision: Union[str, None] = "4d7e9b2c1a85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing tenants remain unassigned and therefore fail closed for
    # CORPORATE_GROUP_ONLY federation until a trusted operator assigns a group.
    op.add_column(
        "tenant_registry",
        sa.Column("corporate_group_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_tenant_registry_corporate_group_id",
        "tenant_registry",
        ["corporate_group_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_registry_corporate_group_id",
        table_name="tenant_registry",
    )
    op.drop_column("tenant_registry", "corporate_group_id")
