"""Testes unitarios do parsing das respostas do modelo (sem rede, sem Ollama).

RespostaChamada1/RespostaChamada2 sao os unicos pontos onde o texto bruto
que o modelo devolve vira dado estruturado -- normalizacoes de quirks reais
de modelo (nao hipoteses) moram aqui.
"""
from app.services.assistente.runtime import RespostaChamada1, RespostaChamada2


class TestNormalizacaoDeLiteralNulo:
    """Achado empirico rodando llama3.1:8b de verdade via Ollama: sob decodificacao
    restrita por JSON Schema, o modelo as vezes preenche um campo Optional com a
    STRING "null" em vez do null JSON -- mesmo quando o schema permite null. Sem
    normalizar isso, "null" vira uma consulta SQL invalida e o pedido cai no
    caminho errado (SQL rejeitado pelo validador) em vez do caminho correto
    (o modelo ja tinha dito, em espirito, "nao ha consulta")."""

    def test_string_null_no_sql_vira_none(self):
        r = RespostaChamada1(sql="null", premissas=[], data_solicitada=None, falta="motivo")
        assert r.sql is None

    def test_variantes_de_literal_nulo_sao_normalizadas(self):
        for literal in ("null", "NULL", "None", "nulo", "n/a", "", "  null  "):
            r = RespostaChamada1(sql=literal, premissas=[], data_solicitada=literal, falta=literal)
            assert r.sql is None
            assert r.data_solicitada is None
            assert r.falta is None

    def test_sql_de_verdade_nao_e_afetado(self):
        sql = "SELECT SUM(valor) FROM vw_despesas_reconciliadas"
        r = RespostaChamada1(sql=sql, premissas=[], data_solicitada="2026-07", falta=None)
        assert r.sql == sql
        assert r.data_solicitada == "2026-07"

    def test_chamada2_tambem_normaliza_falta_e_divergencia(self):
        r = RespostaChamada2(veredito="ok", divergencia="null", premissas=[], falta="None", resposta="ok")
        assert r.divergencia is None
        assert r.falta is None

    def test_none_python_continua_none(self):
        r = RespostaChamada1(sql=None, premissas=[], data_solicitada=None, falta=None)
        assert r.sql is None
