"""4-rewrite-states

Revision ID: 85c8e434c16d
Revises: 902fc606e261
Create Date: 2026-09-12 13:00:00.000000

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "85c8e434c16d"
down_revision: Union[str, Sequence[str], None] = "902fc606e261"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
