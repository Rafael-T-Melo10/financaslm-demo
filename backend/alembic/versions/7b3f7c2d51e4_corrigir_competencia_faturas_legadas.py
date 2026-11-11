"""corrigir competencia de faturas legadas

Revision ID: 7b3f7c2d51e4
Revises: 2fe2b7b86036
Create Date: 2026-07-07 18:45:00.000000

"""
from collections import Counter
from datetime import date, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b3f7c2d51e4'
down_revision: Union[str, None] = '2fe2b7b86036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

faturas = sa.table(
    'faturas',
    sa.column('id', sa.Integer()),
    sa.column('despesa_id', sa.Integer()),
    sa.column('vencimento', sa.Date()),
    sa.column('data_referencia', sa.Date()),
)

fatura_itens = sa.table(
    'fatura_itens',
    sa.column('fatura_id', sa.Integer()),
    sa.column('data', sa.Date()),
)

despesas = sa.table(
    'despesas',
    sa.column('id', sa.Integer()),
    sa.column('data', sa.Date()),
)


def _coerce_date(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            return None
    return None


def _competencia_por_datas(datas_compra, vencimento):
    meses_compras = []
    for valor in datas_compra:
        data_compra = _coerce_date(valor)
        if data_compra:
            meses_compras.append(data_compra.replace(day=1))

    if meses_compras:
        mes_mais_frequente, _ = Counter(meses_compras).most_common(1)[0]
        return mes_mais_frequente

    vencimento_normalizado = _coerce_date(vencimento)
    if vencimento_normalizado:
        return vencimento_normalizado.replace(day=1)

    return date.today().replace(day=1)


def recalcular_competencia_faturas(bind) -> None:
    registros = bind.execute(
        sa.select(
            faturas.c.id,
            faturas.c.despesa_id,
            faturas.c.vencimento,
            faturas.c.data_referencia,
        )
    ).mappings().all()

    for fatura in registros:
        datas_itens = bind.execute(
            sa.select(fatura_itens.c.data).where(fatura_itens.c.fatura_id == fatura['id'])
        ).scalars().all()
        nova_competencia = _competencia_por_datas(datas_itens, fatura['vencimento'])
        competencia_atual = _coerce_date(fatura['data_referencia'])

        if nova_competencia == competencia_atual:
            continue

        bind.execute(
            sa.update(faturas)
            .where(faturas.c.id == fatura['id'])
            .values(data_referencia=nova_competencia)
        )

        if fatura['despesa_id']:
            bind.execute(
                sa.update(despesas)
                .where(despesas.c.id == fatura['despesa_id'])
                .values(data=nova_competencia)
            )


def upgrade() -> None:
    recalcular_competencia_faturas(op.get_bind())


def downgrade() -> None:
    # Migração de reparo de dados. Não há restauração segura da competência incorreta anterior.
    pass
