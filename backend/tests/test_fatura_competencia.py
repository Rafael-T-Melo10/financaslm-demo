from datetime import date

from app.services.importacao import competencia_fatura as _competencia_fatura


def test_competencia_usa_mes_mais_frequente_das_compras():
    """Caso relatado: fatura fecha com compras de junho mas vence em julho.
    A despesa deve ser lançada em junho, não em julho."""
    compras = [
        {"data": date(2026, 6, 3)},
        {"data": date(2026, 6, 15)},
        {"data": date(2026, 6, 28)},
        {"data": date(2026, 7, 1)},  # uma compra já no ciclo seguinte
    ]
    vencimento = date(2026, 7, 10)

    competencia = _competencia_fatura(compras, vencimento)

    assert competencia == date(2026, 6, 1)


def test_competencia_cai_no_vencimento_sem_datas_de_compra():
    vencimento = date(2026, 7, 10)
    assert _competencia_fatura([], vencimento) == date(2026, 7, 1)


def test_competencia_ignora_compras_sem_data_valida():
    compras = [{"data": None}, {"descricao": "sem data"}]
    vencimento = date(2026, 7, 10)
    assert _competencia_fatura(compras, vencimento) == date(2026, 7, 1)


def test_competencia_aceita_datas_iso_em_string():
    compras = [{"data": "2026-06-03"}, {"data": "2026-06-28"}, {"data": "2026-07-01"}]
    vencimento = date(2026, 7, 10)
    assert _competencia_fatura(compras, vencimento) == date(2026, 6, 1)


def test_competencia_sem_vencimento_nem_compras_usa_hoje():
    resultado = _competencia_fatura([], None)
    assert resultado == date.today().replace(day=1)
