"""unificar heads categorias e senhas pdf

Revision ID: f0468fef4ba5
Revises: b3c4d5e6f7a8, c4d5e6f7a8b9
Create Date: 2026-07-20 12:48:49.286555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0468fef4ba5'
down_revision: Union[str, None] = ('b3c4d5e6f7a8', 'c4d5e6f7a8b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
