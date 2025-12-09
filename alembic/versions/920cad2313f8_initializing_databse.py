"""Initializing Databse

Revision ID: 920cad2313f8
Revises: 9a1610655735
Create Date: 2025-12-09 18:41:22.910265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '920cad2313f8'
down_revision: Union[str, Sequence[str], None] = '9a1610655735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
