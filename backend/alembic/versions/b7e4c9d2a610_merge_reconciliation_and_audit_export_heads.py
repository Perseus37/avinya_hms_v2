"""Merge the reconciliation governance and audit export migration branches.

Revision ID: b7e4c9d2a610
Revises: f3a9c2d7e610, a9c4e7b2d610
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7e4c9d2a610"
down_revision: Union[str, Sequence[str], None] = (
    "f3a9c2d7e610",
    "a9c4e7b2d610",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both branches contain independent schema changes already applied by
    # their parent revisions. This revision only joins their migration graph.
    pass


def downgrade() -> None:
    # A merge-point downgrade must not reverse either parent branch.
    pass
