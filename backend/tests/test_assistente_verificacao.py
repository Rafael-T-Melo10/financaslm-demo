"""Testes de checar_afirmacoes -- dois bugs reais achados em uso real (não
mockado) contra llama3.1:latest, via o log de auditoria em produção local:

1. Separador decimal de PONTO: o modelo (treinado majoritariamente em
   inglês) às vezes escreve "R$ 4302.74" em vez de "R$ 4302,74" -- o regex
   antigo só reconhecia vírgula como decimal, então "4302.74" quebrava em
   dois tokens ("4302" e "74"), nenhum batendo com o valor real.
2. NULL de agregação vazia: SUM/COUNT sobre zero linhas casadas devolve
   NULL em SQL, mas a frase natural para isso é sempre "R$ 0,00" ou
   "nenhuma" -- nunca "NULL". Sem tratar isso, toda resposta correta que
   mencionasse "0" para um resultado vazio era rebaixada para nao_sei.
"""
import sqlglot

from app.services.assistente.execucao_sql import ResultadoSql
from app.services.assistente.verificacao import (
    checar_afirmacoes,
    checar_leitura_media_mensal,
    checar_resultado_sem_dados,
)


def _resultado(linhas):
    return ResultadoSql(colunas=list(linhas[0]) if linhas else [], linhas=linhas, truncado=False, tempo_ms=1, dialeto="postgres")


class TestSeparadorDecimalDePontoEVirgula:
    def test_numero_com_ponto_decimal_bate_com_valor_real(self):
        resultado = _resultado([{"total_gasto": 4302.74}])
        assert checar_afirmacoes("Você gastou R$ 4302.74 este mês.", resultado) == []

    def test_numero_com_virgula_decimal_continua_batendo(self):
        resultado = _resultado([{"total_gasto": 4302.74}])
        assert checar_afirmacoes("Você gastou R$ 4302,74 este mês.", resultado) == []

    def test_numero_agrupado_por_milhar_com_virgula_decimal(self):
        resultado = _resultado([{"total": 1204.55}])
        assert checar_afirmacoes("O total foi R$ 1.204,55.", resultado) == []

    def test_numero_com_duas_casas_e_ponto_isolado_bate(self):
        resultado = _resultado([{"total": 98.8}])
        assert checar_afirmacoes("Você gastou R$98.80 com Alimentação.", resultado) == []

    def test_numero_inventado_com_ponto_decimal_ainda_e_pego(self):
        resultado = _resultado([{"total": 100.0}])
        assert checar_afirmacoes("Você gastou R$ 9999.99.", resultado) != []

    def test_numero_inventado_com_virgula_decimal_ainda_e_pego(self):
        resultado = _resultado([{"total": 100.0}])
        assert checar_afirmacoes("Você gastou R$ 9.999,99.", resultado) != []


class TestNumeroEcoadoDaPergunta:
    """Achado ao vivo: 'Qual a média de gastos dos últimos 3 meses em luz?'
    -- a resposta ecoava o "3 meses" da própria pergunta, e esse "3" nunca
    aparece no resultado (é um parâmetro de filtro, não uma coluna de
    saída), então era sinalizado como número inventado."""

    def test_numero_da_pergunta_ecoado_na_resposta_nao_e_sinalizado(self):
        resultado = _resultado([{"media_gasto": None}])
        pergunta = "Qual a média de gastos dos últimos 3 meses em luz?"
        resposta = "Não encontrei gastos com luz nos últimos 3 meses."
        assert checar_afirmacoes(resposta, resultado, pergunta) == []

    def test_numero_formatado_da_pergunta_tambem_e_reconhecido(self):
        resultado = _resultado([{"total": None}])
        pergunta = "Tive alguma compra acima de R$ 5.000 este ano?"
        resposta = "Não encontrei nenhuma compra acima de R$ 5.000."
        assert checar_afirmacoes(resposta, resultado, pergunta) == []

    def test_numero_que_nao_esta_na_pergunta_nem_no_resultado_continua_pego(self):
        resultado = _resultado([{"media_gasto": None}])
        pergunta = "Qual a média de gastos dos últimos 3 meses em luz?"
        resposta = "A média foi de 7 meses consecutivos."
        assert checar_afirmacoes(resposta, resultado, pergunta) != []


class TestNullDeAgregacaoVazia:
    def test_resposta_menciona_zero_quando_sum_e_null(self):
        resultado = _resultado([{"valor_total": None}])
        assert checar_afirmacoes("Você não tem despesas recorrentes ativas (R$ 0,00).", resultado) == []

    def test_resposta_menciona_apenas_digito_zero(self):
        resultado = _resultado([{"valor_total": None}])
        assert checar_afirmacoes("O total é 0.", resultado) == []

    def test_numero_nao_zero_continua_sem_suporte_quando_resultado_e_null(self):
        resultado = _resultado([{"valor_total": None}])
        assert checar_afirmacoes("Você tem R$ 150,00 em despesas recorrentes.", resultado) != []


def _arvore(sql, dialeto="postgres"):
    return sqlglot.parse_one(sql, read=dialeto)


class TestChecarLeituraMediaMensal:
    """checar_leitura_media_mensal -- guarda-corpo achado ao vivo (ver plano da mudança): o
    screenshot trazido pelo usuário mostrava a premissa "leitura mensal" declarada mas o SQL de
    fato executado era AVG(valor) direto sobre os lançamentos (leitura por lançamento), um
    resultado que não corresponde a nenhuma das duas leituras com garantia."""

    _SQL_AVG_DIRETO = (
        "SELECT ROUND(AVG(valor), 2) AS media_mensal FROM vw_despesas_reconciliadas "
        "WHERE categoria = 'Alimentação' AND data_competencia BETWEEN CURRENT_DATE - INTERVAL '3 months' AND CURRENT_DATE"
    )
    _SQL_SUBCONSULTA_MENSAL = (
        "SELECT ROUND(AVG(total_mes), 2) AS media_mensal FROM (SELECT to_char(data_competencia, 'YYYY-MM') AS mes, "
        "SUM(valor) AS total_mes FROM vw_despesas_reconciliadas WHERE categoria = 'Alimentação' "
        "AND data_competencia >= CURRENT_DATE - INTERVAL '3 months' GROUP BY 1) sub"
    )
    _SQL_CTE_MENSAL = (
        "WITH totais AS (SELECT to_char(data_competencia, 'YYYY-MM') AS mes, SUM(valor) AS total_mes "
        "FROM vw_despesas_reconciliadas WHERE categoria = 'Alimentação' GROUP BY 1) "
        "SELECT ROUND(AVG(total_mes), 2) AS media_mensal FROM totais"
    )

    def test_avg_direto_sobre_a_view_e_sinalizado_por_padrao(self):
        pergunta = "qual é a media de gastos em alimentação nos ultimos 3 meses?"
        assert checar_leitura_media_mensal(pergunta, _arvore(self._SQL_AVG_DIRETO)) is not None

    def test_subconsulta_com_group_by_mensal_nao_e_sinalizada(self):
        pergunta = "qual é a media de gastos em alimentação nos ultimos 3 meses?"
        assert checar_leitura_media_mensal(pergunta, _arvore(self._SQL_SUBCONSULTA_MENSAL)) is None

    def test_cte_com_group_by_mensal_nao_e_sinalizada(self):
        pergunta = "qual a média mensal de gastos com Alimentação?"
        assert checar_leitura_media_mensal(pergunta, _arvore(self._SQL_CTE_MENSAL)) is None

    def test_pedido_explicito_por_lancamento_aceita_avg_direto(self):
        pergunta = "qual a média de gasto por compra no mercado?"
        assert checar_leitura_media_mensal(pergunta, _arvore(self._SQL_AVG_DIRETO)) is None

    def test_pedido_por_transacao_tambem_aceita_avg_direto(self):
        pergunta = "qual a média de gasto por transação em 2025?"
        assert checar_leitura_media_mensal(pergunta, _arvore(self._SQL_AVG_DIRETO)) is None

    def test_pergunta_sem_media_nao_e_checada(self):
        pergunta = "quanto eu gastei em alimentação nos últimos 3 meses?"
        sql_total = "SELECT SUM(valor) AS total FROM vw_despesas_reconciliadas WHERE categoria = 'Alimentação'"
        assert checar_leitura_media_mensal(pergunta, _arvore(sql_total)) is None


class TestChecarResultadoSemDados:
    """checar_resultado_sem_dados -- achado real (ver plano da mudança): uma consulta de "média
    mensal" (AVG escalar por fora de uma subconsulta com GROUP BY por mês) sobre um período sem
    nenhum lançamento devolve `[{"media_mensal": None}]` -- UMA linha com valor None, não uma lista
    vazia, porque agregado escalar sem GROUP BY sempre devolve exatamente uma linha em SQL. O
    Phi-4 Mini bateu nesse caso (período hardcoded 3 anos no passado) e o veredito "ressalva" com
    resposta "n/a" escondia que não havia dado nenhum."""

    _SQL_MEDIA_MENSAL = (
        "SELECT ROUND(AVG(total_mes), 2) AS media_mensal FROM (SELECT to_char(data_competencia, 'YYYY-MM') AS mes, "
        "SUM(valor) AS total_mes FROM vw_despesas_reconciliadas WHERE categoria = 'Alimentação' "
        "AND data_competencia BETWEEN '2015-01-01' AND '2015-03-31' GROUP BY 1) sub"
    )
    _SQL_SUM_TOTAL = "SELECT SUM(valor) AS total FROM vw_despesas_reconciliadas WHERE categoria = 'Lazer'"

    def test_lista_vazia_e_sinalizada(self):
        resultado = _resultado([])
        assert checar_resultado_sem_dados(resultado, None) is True

    def test_avg_escalar_com_linha_unica_null_e_sinalizada(self):
        resultado = _resultado([{"media_mensal": None}])
        assert checar_resultado_sem_dados(resultado, _arvore(self._SQL_MEDIA_MENSAL)) is True

    def test_sum_com_linha_unica_null_nao_e_sinalizada(self):
        """SUM/COUNT sobre zero linhas devolvendo NULL tem leitura legítima de "R$0,00" -- já
        aceito por checar_afirmacoes (TestNullDeAgregacaoVazia acima); esta função não deve tratar
        isso como "sem dados" só porque não tem AVG na consulta."""
        resultado = _resultado([{"total": None}])
        assert checar_resultado_sem_dados(resultado, _arvore(self._SQL_SUM_TOTAL)) is False

    def test_linha_unica_com_valor_real_nao_e_sinalizada(self):
        resultado = _resultado([{"media_mensal": 662.44}])
        assert checar_resultado_sem_dados(resultado, _arvore(self._SQL_MEDIA_MENSAL)) is False

    def test_resultado_none_nao_e_sinalizado(self):
        assert checar_resultado_sem_dados(None, None) is False
