"""Merge procurement audit and pharmacy stock-control migration heads."""

from typing import Sequence, Union

revision: str = "8b6d2f4a9c10"
down_revision: Union[str, Sequence[str], None] = (
    "d6a84c2f91b0",
    "f3a8c1d9e620",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
