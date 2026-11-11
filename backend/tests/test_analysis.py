import re
from datetime import date
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta

from app.services.analysis import (
    calcular_analise_gastos,
    calcular_gastos_mensais,
    gerar_alertas,
    montar_dashboard,
    previsao_gastos,
)


def despesa(valor, data, categoria="Outros"):
    return SimpleNamespace(valor=valor, data=data, categoria=categoria)


def receita(valor, data):
    return SimpleNamespace(valor=valor, data=data)


def parcela(valor_parcela, data_proxima, pago=False):
    return SimpleNamespace(valor_parcela=valor_parcela, data_proxima_parcela=data_proxima, pago=pago)


def cartao(nome="Cartão", limite=1000, saldo_usado=0, ativo=True, id=1):
    return SimpleNamespace(nome=nome, limite=limite, saldo_usado=saldo_usado, ativo=ativo, id=id)


def test_gastos_mensais_chave_iso():
    gastos = calcular_gastos_mensais([despesa(10, date(2026, 7, 5)), despesa(5, date(2026, 7, 20))])
    assert gastos == {"2026-07": 15.0}


def test_previsao_usa_media_mensal_por_categoria():
    # Mês 1: duas compras de mercado (100 + 200). Mês 2: uma de 300.
    # Média MENSAL correta = 300; média por transação (bug antigo) daria 200.
    despesas = [
        despesa(100, date(2026, 5, 3), "Alimentação"),
        despesa(200, date(2026, 5, 20), "Alimentação"),
        despesa(300, date(2026, 6, 10), "Alimentação"),
    ]

    resultado = previsao_gastos(despesas, [], meses=1)
    mes = resultado["previsao"][0]

    assert mes["previsao_categorias"]["Alimentação"] == 300.0
    assert mes["total_estimado_despesas"] == 300.0


def test_previsao_mes_formato_iso_e_meses_corretos():
    resultado = previsao_gastos([despesa(50, date(2026, 1, 1))], [], meses=3)
    meses = [item["mes"] for item in resultado["previsao"]]

    assert all(re.fullmatch(r"\d{4}-\d{2}", mes) for mes in meses)

    esperados = [(date.today() + relativedelta(months=i)).strftime("%Y-%m") for i in range(1, 4)]
    assert meses == esperados


def test_previsao_soma_parcelas_do_mes_certo():
    proximo_mes = date.today() + relativedelta(months=1)
    parcelas = [
        parcela(120, proximo_mes),
        parcela(80, proximo_mes),
        parcela(999, proximo_mes, pago=True),  # paga: não entra
        parcela(50, proximo_mes + relativedelta(months=1)),  # outro mês
    ]

    resultado = previsao_gastos([despesa(10, date(2026, 1, 1))], parcelas, meses=1)
    assert resultado["previsao"][0]["total_parcelas"] == 200.0


def test_analise_filtra_por_mes():
    receitas = [receita(1000, date(2026, 7, 1)), receita(500, date(2026, 6, 1))]
    despesas = [despesa(300, date(2026, 7, 10)), despesa(999, date(2026, 6, 10))]

    resultado = calcular_analise_gastos(receitas, despesas, [], [], mes=7, ano=2026)

    assert resultado["total_receitas"] == 1000.0
    assert resultado["total_despesas"] == 300.0
    assert resultado["saldo"] == 700.0


def test_alertas_cartao_e_saldo():
    alertas = gerar_alertas(
        receitas=[receita(100, date(2026, 7, 1))],
        despesas=[despesa(150, date(2026, 7, 1))],
        cartoes=[cartao(nome="Nubank", limite=1000, saldo_usado=900)],
        parcelas=[],
    )

    tipos = {alerta["tipo"] for alerta in alertas}
    assert "AVISO" in tipos  # gastos > receitas
    assert "CRÍTICO" in tipos  # cartão > 80%


def test_dashboard_soma_compromissos_pendentes_sem_alterar_saldo_lancado():
    hoje = date.today()
    receita_mes = SimpleNamespace(id=1, valor=1000, data=hoje, descricao="Salário", origem="manual")
    despesa_mes = SimpleNamespace(id=1, valor=200, data=hoje, descricao="Mercado", categoria="Alimentação", origem="manual")
    parcela_aberta = SimpleNamespace(
        id=1, pago=False, parcelas_restantes=1, data_proxima_parcela=hoje,
        valor_parcela=120, descricao="Notebook",
    )
    recorrente_aberta = SimpleNamespace(
        id=1, ativo=True, data_inicio=hoje - relativedelta(months=1), ultima_geracao=None,
        dia_vencimento=hoje.day, valor=80, descricao="Internet",
    )

    resultado = montar_dashboard(
        [receita_mes], [despesa_mes], [], [], [parcela_aberta], [recorrente_aberta], [], hoje.month, hoje.year
    )

    assert resultado["resumo"]["saldo_lancado"] == 800
    assert resultado["resumo"]["compromissos_pendentes"] == 200
    assert resultado["resumo"]["saldo_projetado"] == 600


def test_dashboard_categoriza_itens_da_fatura_sem_duplicar_total():
    referencia = date(2026, 5, 10)
    despesa_fatura = SimpleNamespace(
        id=10, valor=100, data=referencia, descricao="Fatura", categoria="Cartão de Crédito", origem="fatura"
    )
    itens = [
        SimpleNamespace(descricao="Mercado", categoria="Alimentação", data=referencia, valor=60),
        SimpleNamespace(descricao="Uber", categoria="Transporte", data=referencia, valor=40),
    ]
    fatura = SimpleNamespace(id=1, despesa_id=10, data_referencia=referencia, vencimento=None, valor_total=100, descricao="Fatura", itens=itens, cartao_id=1)

    resultado = montar_dashboard([], [despesa_fatura], [fatura], [], [], [], [], 5, 2026)
    categorias = {item["nome"]: item["valor"] for item in resultado["categorias"]}

    assert categorias == {"Alimentação": 60.0, "Transporte": 40.0}
    assert resultado["resumo"]["despesas_lancadas"] == 100


def test_dashboard_mes_futuro_nao_exibe_comparacoes():
    futuro = date.today() + relativedelta(months=2)
    resultado = montar_dashboard([], [], [], [], [], [], [], futuro.month, futuro.year)

    assert resultado["periodo"]["status"] == "futuro"
    assert resultado["resumo"]["comparacao_mes_anterior"] is None
    assert resultado["resumo"]["comparacao_media_3_meses"] is None


def test_dashboard_normaliza_variantes_e_remove_categorias_zeradas():
    atual = date(2026, 7, 10)
    anterior = date(2026, 6, 10)
    despesas = [
        SimpleNamespace(id=1, valor=60, data=atual, descricao="Mercado", categoria="Alimentacao", origem="manual"),
        SimpleNamespace(id=2, valor=40, data=atual, descricao="Restaurante", categoria="Alimentação", origem="manual"),
        SimpleNamespace(id=3, valor=25, data=atual, descricao="Cinema", categoria="Diversão", origem="manual"),
        SimpleNamespace(id=4, valor=50, data=anterior, descricao="Farmácia", categoria="Saude", origem="manual"),
    ]

    resultado = montar_dashboard([], despesas, [], [], [], [], [], 7, 2026)
    categorias = {item["nome"]: item for item in resultado["categorias"]}

    assert categorias["Alimentação"]["valor"] == 100
    assert categorias["Lazer"]["valor"] == 25
    assert "Saúde" not in categorias
    assert sum(item["percentual"] for item in categorias.values() if item["percentual"] is not None) == 100


def test_dashboard_ajuste_nao_distorce_percentual_de_gastos():
    referencia = date(2026, 7, 10)
    despesa_fatura = SimpleNamespace(
        id=10, valor=90, data=referencia, descricao="Fatura", categoria="Cartão de Crédito", origem="fatura"
    )
    itens = [SimpleNamespace(descricao="Mercado", categoria="Alimentação", data=referencia, valor=100)]
    fatura = SimpleNamespace(
        id=1, despesa_id=10, data_referencia=referencia, vencimento=None,
        valor_total=90, descricao="Fatura", itens=itens, cartao_id=1,
    )

    resultado = montar_dashboard([], [despesa_fatura], [fatura], [], [], [], [], 7, 2026)
    categorias = {item["nome"]: item for item in resultado["categorias"]}

    assert categorias["Alimentação"]["percentual"] == 100
    assert categorias["Ajustes da fatura"]["percentual"] is None
    assert categorias["Ajustes da fatura"]["valor"] == -10


def test_dashboard_projeta_seis_meses_e_agrupa_parcelas_vencidas():
    hoje = date.today()
    parcelas = [
        SimpleNamespace(
            id=indice, pago=False, parcelas_restantes=1,
            data_proxima_parcela=hoje - relativedelta(days=indice),
            valor_parcela=100, descricao=f"Parcela {indice}",
        )
        for indice in range(1, 5)
    ]

    resultado = montar_dashboard([], [], [], [], parcelas, [], [], hoje.month, hoje.year)
    alertas_vencidos = [item for item in resultado["alertas"] if item["chave"] == "financeiro:parcelas-vencidas"]

    assert len(resultado["projecao_compromissos"]) == 6
    assert len(alertas_vencidos) == 1
    assert "4 parcela(s)" in alertas_vencidos[0]["mensagem"]
