"""progresso de sincronizacao gmail

Revision ID: c1393c66bef8
Revises: 4959bb1c4b37
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1393c66bef8'
down_revision: Union[str, None] = '4959bb1c4b37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gmail_conexoes', sa.Column('sincronizando', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('gmail_conexoes', sa.Column('sync_total', sa.Integer(), nullable=True))
    op.add_column('gmail_conexoes', sa.Column('sync_processados', sa.Integer(), nullable=True))
    op.add_column('gmail_conexoes', sa.Column('sync_iniciado_em', sa.DateTime(), nullable=True))
    op.add_column('gmail_conexoes', sa.Column('ultimo_resumo_encontrados', sa.Integer(), nullable=True))
    op.add_column('gmail_conexoes', sa.Column('ultimo_resumo_novos', sa.Integer(), nullable=True))
    op.add_column('gmail_conexoes', sa.Column('ultimo_resumo_erros', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('gmail_conexoes', 'ultimo_resumo_erros')
    op.drop_column('gmail_conexoes', 'ultimo_resumo_novos')
    op.drop_column('gmail_conexoes', 'ultimo_resumo_encontrados')
    op.drop_column('gmail_conexoes', 'sync_iniciado_em')
    op.drop_column('gmail_conexoes', 'sync_processados')
    op.drop_column('gmail_conexoes', 'sync_total')
    op.drop_column('gmail_conexoes', 'sincronizando')
