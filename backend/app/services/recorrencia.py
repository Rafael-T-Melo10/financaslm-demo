import calendar
from datetime import date

from sqlalchemy.orm import Session

from app import models


def gerar_despesas_pendentes(db: Session, usuario_id: int) -> int:
    """Cria a Despesa do mês para toda recorrência ativa cujo mês ainda não foi lançado.

    Idempotente: chamar mais de uma vez no mesmo mês não duplica despesas.
    """
    hoje = date.today()
    mes_atual = hoje.replace(day=1)

    recorrentes = db.query(models.DespesaRecorrente).filter(
        models.DespesaRecorrente.usuario_id == usuario_id,
        models.DespesaRecorrente.ativo == True,  # noqa: E712
        models.DespesaRecorrente.data_inicio <= hoje,
    ).all()

    geradas = 0
    for recorrente in recorrentes:
        ultimo_mes_gerado = recorrente.ultima_geracao.replace(day=1) if recorrente.ultima_geracao else None
        if ultimo_mes_gerado and ultimo_mes_gerado >= mes_atual:
            continue

        ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]
        dia = min(recorrente.dia_vencimento, ultimo_dia_mes)

        db.add(models.Despesa(
            usuario_id=usuario_id,
            cartao_id=recorrente.cartao_id,
            descricao=recorrente.descricao,
            valor=recorrente.valor,
            categoria=recorrente.categoria,
            data=hoje.replace(day=dia),
            origem="recorrente",
        ))
        recorrente.ultima_geracao = mes_atual
        geradas += 1

    if geradas:
        db.commit()

    return geradas
