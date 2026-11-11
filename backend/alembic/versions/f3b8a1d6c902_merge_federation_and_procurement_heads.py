"""merge federation audit and patient-indent procurement migration heads

Revision ID: f3b8a1d6c902
Revises: a7c4e9d2b615, e8a4c1d7f620
Create Date: 2026-11-11
"""

# This is an explicit graph merge only. Both parent revisions contain their
# own schema changes; this revision intentionally performs no DDL.
revision = "f3b8a1d6c902"
down_revision = ("a7c4e9d2b615", "e8a4c1d7f620")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
