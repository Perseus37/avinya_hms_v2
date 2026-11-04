"""add hospital group owner role and single-use invitations

Revision ID: 9c31a7e5b204
Revises: 6a2f9c4d1e80
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c31a7e5b204"
down_revision: Union[str, None] = "6a2f9c4d1e80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_users",
        sa.Column("group_role", sa.String(30), server_default="STAFF", nullable=False),
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("hospital_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_user_id", sa.Integer(), sa.ForeignKey("organization_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_normalized", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("invitation_type", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_organization_invitations_token_hash"),
    )
    op.create_index(
        "ix_org_invitations_group_email_status",
        "organization_invitations",
        ["group_id", "email_normalized", "accepted_at", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_invitations_group_email_status", table_name="organization_invitations")
    op.drop_table("organization_invitations")
    op.drop_column("organization_users", "group_role")
