"""dinheiro em numeric

Revision ID: cbd208c4db8d
Revises: ac4335e128ff
Create Date: 2026-07-06 14:29:32.241739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbd208c4db8d'
down_revision: Union[str, None] = 'ac4335e128ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Bancos criados antes do alembic guardavam dinheiro em Float.
# Em bancos novos a migração inicial já cria Numeric e este alter é inócuo.
COLUNAS = [
    ("receitas", "valor", False),
    ("despesas", "valor", False),
    ("cartoes_credito", "limite", True),
    ("cartoes_credito", "saldo_usado", True),
    ("faturas", "valor_total", False),
    ("fatura_itens", "valor", False),
    ("parcelas", "valor_total", False),
    ("parcelas", "valor_parcela", False),
]


def upgrade() -> None:
    for tabela, coluna, nullable in COLUNAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.alter_column(
                coluna,
                existing_type=sa.Float(),
                type_=sa.Numeric(10, 2),
                existing_nullable=nullable,
            )


def downgrade() -> None:
    for tabela, coluna, nullable in COLUNAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.alter_column(
                coluna,
                existing_type=sa.Numeric(10, 2),
                type_=sa.Float(),
                existing_nullable=nullable,
            )
