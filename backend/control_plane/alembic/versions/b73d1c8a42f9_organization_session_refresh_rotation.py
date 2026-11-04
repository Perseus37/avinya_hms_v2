"""add rotating refresh tokens and device metadata to organization sessions

Revision ID: b73d1c8a42f9
Revises: 9c31a7e5b204
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b73d1c8a42f9"
down_revision: Union[str, None] = "9c31a7e5b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_sessions",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organization_sessions",
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_sessions",
        sa.Column("device_label", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "organization_sessions",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_organization_sessions_refresh_token_hash",
        "organization_sessions",
        ["refresh_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_organization_sessions_refresh_token_hash",
        table_name="organization_sessions",
    )
    op.drop_column("organization_sessions", "last_used_at")
    op.drop_column("organization_sessions", "device_label")
    op.drop_column("organization_sessions", "refresh_expires_at")
    op.drop_column("organization_sessions", "refresh_token_hash")
