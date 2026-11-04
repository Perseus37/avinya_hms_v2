"""add hospital-group staff identity and branch membership foundations

Revision ID: 6a2f9c4d1e80
Revises: 4d7e9b2c1a85
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a2f9c4d1e80"
down_revision: Union[str, None] = "4d7e9b2c1a85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospital_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(63), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hospital_groups_code", "hospital_groups", ["code"], unique=True)

    op.create_table(
        "organization_branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("hospital_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_registry_id", sa.Integer(), sa.ForeignKey("tenant_registry.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_registry_id", name="uq_org_branch_tenant_registry"),
        sa.UniqueConstraint("group_id", "code", name="uq_org_branch_group_code"),
    )
    op.create_index("ix_org_branches_group_status", "organization_branches", ["group_id", "status"])

    op.create_table(
        "organization_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("hospital_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_normalized", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="INVITED", nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("mfa_last_used_counter", sa.Integer(), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "email_normalized", name="uq_org_user_group_email"),
    )
    op.create_index("ix_org_users_group_status", "organization_users", ["group_id", "status"])

    op.create_table(
        "branch_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_user_id", sa.Integer(), sa.ForeignKey("organization_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("organization_branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), server_default="INVITED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_user_id", "branch_id", name="uq_branch_membership_user_branch"),
    )
    op.create_index("ix_branch_memberships_branch_status", "branch_memberships", ["branch_id", "status"])

    op.create_table(
        "branch_membership_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("branch_memberships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_code", sa.String(100), nullable=False),
        sa.UniqueConstraint("membership_id", "role_code", name="uq_membership_role_code"),
    )
    op.create_index("ix_branch_membership_roles_membership_id", "branch_membership_roles", ["membership_id"])

    op.create_table(
        "branch_department_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("branch_memberships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_code", sa.String(100), nullable=False),
        sa.UniqueConstraint("membership_id", "department_code", name="uq_membership_department_code"),
    )
    op.create_index("ix_branch_department_assignments_membership_id", "branch_department_assignments", ["membership_id"])

    op.create_table(
        "branch_user_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("branch_memberships.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("organization_user_id", sa.Integer(), sa.ForeignKey("organization_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("organization_branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("local_user_id", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("membership_id", name="uq_branch_user_link_membership"),
        sa.UniqueConstraint("branch_id", "local_user_id", name="uq_branch_user_link_local_user"),
    )
    op.create_index("ix_branch_user_links_org_user", "branch_user_links", ["organization_user_id"])

    op.create_table(
        "organization_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_user_id", sa.Integer(), sa.ForeignKey("organization_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_organization_sessions_token_hash"),
    )
    op.create_index("ix_organization_sessions_organization_user_id", "organization_sessions", ["organization_user_id"])

    op.create_table(
        "branch_access_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_session_id", sa.Integer(), sa.ForeignKey("organization_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("branch_memberships.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_branch_access_sessions_token_hash"),
    )
    op.create_index("ix_branch_access_sessions_organization_session_id", "branch_access_sessions", ["organization_session_id"])
    op.create_index("ix_branch_access_membership_expiry", "branch_access_sessions", ["membership_id", "expires_at"])


def downgrade() -> None:
    op.drop_table("branch_access_sessions")
    op.drop_table("organization_sessions")
    op.drop_table("branch_user_links")
    op.drop_table("branch_department_assignments")
    op.drop_table("branch_membership_roles")
    op.drop_table("branch_memberships")
    op.drop_table("organization_users")
    op.drop_table("organization_branches")
    op.drop_table("hospital_groups")
