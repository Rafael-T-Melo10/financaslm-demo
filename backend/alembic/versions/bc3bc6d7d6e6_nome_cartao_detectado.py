"""nome do cartao detectado na importacao pendente

Revision ID: bc3bc6d7d6e6
Revises: c1393c66bef8
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc3bc6d7d6e6'
down_revision: Union[str, None] = 'c1393c66bef8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('importacoes_pendentes', sa.Column('nome_cartao_detectado', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('importacoes_pendentes', 'nome_cartao_detectado')
