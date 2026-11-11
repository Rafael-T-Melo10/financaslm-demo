"""adiciona tabela receita_itens para detalhamento de holerite

Revision ID: 4959bb1c4b37
Revises: abe3769f0a24
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4959bb1c4b37'
down_revision: Union[str, None] = 'abe3769f0a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'receita_itens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receita_id', sa.Integer(), nullable=False),
        sa.Column('descricao', sa.String(length=255), nullable=False),
        sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('data_criacao', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['receita_id'], ['receitas.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('receita_itens')
