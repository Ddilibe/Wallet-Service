"""Remved username from user table


Revision ID: 8b036996319a
Revises: 53380654ce05
Create Date: 2025-12-09 22:36:26.068551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b036996319a'
down_revision: Union[str, Sequence[str], None] = '53380654ce05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
