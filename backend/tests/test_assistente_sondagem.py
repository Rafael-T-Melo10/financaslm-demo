"""Testes de extrair_periodo -- em particular o padrão "últimos N meses/anos" (ver plano da
mudança: era o único caso do gabarito, e dos dois exemplos trazidos pelo usuário, que a sondagem
não reconhecia, deixando o modelo calcular CURRENT_DATE - INTERVAL sozinho sem checagem
antecipada de zero-dado nem data literal no prompt)."""
from datetime import date

from app.services.assistente.sondagem import extrair_periodo


class TestUltimosNMeses:
    def test_ultimos_3_meses(self):
        periodo = extrair_periodo("qual é a media de gastos em alimentação nos ultimos 3 meses?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2026, 5, 23)
        assert periodo.fim == date(2026, 8, 23)

    def test_ultimos_6_meses_com_acento(self):
        periodo = extrair_periodo("quanto gastei nos últimos 6 meses?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2026, 2, 23)
        assert periodo.fim == date(2026, 8, 23)

    def test_ultimos_12_meses(self):
        periodo = extrair_periodo("em quais dos últimos 12 meses eu gastei mais de 5000?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2025, 8, 23)

    def test_ultimos_2_anos(self):
        periodo = extrair_periodo("quanto eu paguei de luz nos últimos 2 anos?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2024, 8, 23)
        assert periodo.fim == date(2026, 8, 23)

    def test_janela_nao_alinha_a_mes_civil(self):
        """Diferente de _periodo_mes/_periodo_ano -- "últimos N meses" é uma janela corrida
        terminando hoje, não o primeiro/último dia de um mês/ano civil."""
        periodo = extrair_periodo("quanto gastei nos últimos 3 meses?", date(2026, 8, 5))
        assert periodo is not None
        assert periodo.inicio == date(2026, 5, 5)
        assert periodo.fim == date(2026, 8, 5)


class TestPadroesExistentesContinuamFuncionando:
    def test_mes_passado(self):
        periodo = extrair_periodo("quanto gastei mês passado?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2026, 7, 1)
        assert periodo.fim == date(2026, 7, 31)

    def test_ano_atual(self):
        periodo = extrair_periodo("quanto gastei este ano?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2026, 1, 1)
        assert periodo.fim == date(2026, 12, 31)

    def test_nome_de_mes(self):
        periodo = extrair_periodo("quanto gastei em julho de 2026?", date(2026, 8, 23))
        assert periodo is not None
        assert periodo.inicio == date(2026, 7, 1)
        assert periodo.fim == date(2026, 7, 31)

    def test_sem_periodo_reconhecido(self):
        assert extrair_periodo("quanto eu gastei com Netflix?", date(2026, 8, 23)) is None
