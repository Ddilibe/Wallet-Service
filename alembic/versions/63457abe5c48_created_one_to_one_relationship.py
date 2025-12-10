"""Created one to one relationship

Revision ID: 63457abe5c48
Revises: 8b036996319a
Create Date: 2025-12-10 11:31:43.167326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63457abe5c48'
down_revision: Union[str, Sequence[str], None] = '8b036996319a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
