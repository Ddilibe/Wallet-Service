"""Creating Transaction

Revision ID: 10c44b85d7d4
Revises: 920cad2313f8
Create Date: 2025-12-09 18:44:54.712989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10c44b85d7d4'
down_revision: Union[str, Sequence[str], None] = '920cad2313f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
