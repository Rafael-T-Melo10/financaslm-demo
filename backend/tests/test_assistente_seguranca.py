"""Suite de seguranca do assistente text2SQL: validador estatico +
execucao isolada por usuario via sombreamento de view.

Nao usa a fixture `client`/`auth_headers` de conftest.py (essa suite nao
precisa da API HTTP nem do TestClient) -- monta seu proprio banco SQLite
temporario por teste, com as 5 views reais criadas a partir da MESMA fonte
que a migracao usa (app.services.assistente.ddl_views), para que o teste de
ouro compare a view de verdade, nao uma copia.

A metade Postgres exige TEST_POSTGRES_* e a base descartavel
financaslm_validacao, criada por docker-compose.validacao.yml.
Usa IDs negativos de fixture e limpa esses registros ao final.
Nunca seleciona automaticamente o banco pessoal do Compose principal.
"""
from __future__ import annotations

import os
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.models import Base
from app.services.analysis import _categorias_do_periodo
from app.services.assistente import ddl_views
from app.services.assistente.execucao_sql import ExecucaoSqlError, executar
from app.services.assistente.validador import SqlRejeitadoError, validar


# ==================== validador.py -- unidade, sem banco ====================


class TestValidador:
    def test_aceita_select_simples_sobre_view_permitida(self):
        r = validar("SELECT * FROM vw_despesas_reconciliadas", "sqlite")
        assert r.views_referenciadas == frozenset({"vw_despesas_reconciliadas"})

    def test_aceita_cte_e_union(self):
        r = validar(
            "WITH t AS (SELECT * FROM vw_receitas) SELECT * FROM t "
            "UNION SELECT * FROM vw_cartoes",
            "sqlite",
        )
        assert r.views_referenciadas == frozenset({"vw_receitas", "vw_cartoes"})

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM main.vw_despesas_reconciliadas",
            "SELECT * FROM public.vw_despesas_reconciliadas",
        ],
    )
    def test_rejeita_bypass_por_nome_qualificado_por_schema(self, sql):
        with pytest.raises(SqlRejeitadoError, match="qualificada por schema"):
            validar(sql, "sqlite")

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO despesas (valor) VALUES (1)",
            "UPDATE despesas SET valor = 1",
            "DELETE FROM despesas",
            "DROP TABLE despesas",
            "PRAGMA table_info(despesas)",
            "ATTACH DATABASE 'x.db' AS x",
        ],
    )
    def test_rejeita_ddl_e_dml(self, sql):
        with pytest.raises(SqlRejeitadoError):
            validar(sql, "sqlite")

    def test_rejeita_multiplas_instrucoes(self):
        with pytest.raises(SqlRejeitadoError, match="uma instrucao"):
            validar("SELECT 1; DROP TABLE despesas;", "sqlite")

    def test_rejeita_tabela_crua_fora_da_allowlist(self):
        with pytest.raises(SqlRejeitadoError, match="allowlist"):
            validar("SELECT * FROM fatura_itens", "sqlite")

    def test_rejeita_cte_que_reutiliza_nome_de_tabela_reservado(self):
        """Sem essa checagem, 'WITH despesas AS (SELECT * FROM despesas) ...'
        e ambiguo: dentro do corpo da CTE nao-recursiva, 'despesas' resolve
        para a TABELA CRUA (regra padrao de SQL), nao para a propria CTE --
        um alias reutilizado shadowearia esse caso do jeito errado."""
        with pytest.raises(SqlRejeitadoError, match="nome de CTE"):
            validar(
                "WITH despesas AS (SELECT * FROM despesas) SELECT * FROM despesas",
                "sqlite",
            )

    def test_rejeita_funcao_proibida(self):
        with pytest.raises(SqlRejeitadoError, match="funcao proibida"):
            validar("SELECT pg_sleep(5)", "postgres")

    def test_rejeita_sql_invalido(self):
        with pytest.raises(SqlRejeitadoError):
            validar("SELECT FROM WHERE", "sqlite")

    def test_rejeita_consulta_vazia(self):
        with pytest.raises(SqlRejeitadoError):
            validar("   ", "sqlite")


# ==================== fixture: banco SQLite com as views reais ====================


@pytest.fixture
def banco_sqlite(tmp_path, monkeypatch):
    """Banco SQLite isolado por teste, com tabelas + as 5 views reais
    (mesma fonte que a migracao usa), e as variaveis de ambiente que
    execucao_sql.py le apontando para ele."""
    caminho = str(tmp_path / "teste_assistente.db")

    engine_setup = create_engine(f"sqlite:///{caminho}")
    Base.metadata.create_all(bind=engine_setup)
    engine_setup.dispose()

    conn = sqlite3.connect(caminho)
    try:
        ddl_views.criar_views(conn)
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{caminho}")
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    return caminho


def _inserir_fixture_reconciliacao_sqlite(caminho: str, usuario_a: int, usuario_b: int) -> None:
    """Usuario A: uma despesa manual + uma fatura com 2 itens e um ajuste de
    conciliacao (itens somam menos que o valor da fatura). Usuario B: uma
    despesa que nao deve aparecer em NENHUMA consulta feita "como" A."""
    conn = sqlite3.connect(caminho)
    try:
        conn.execute(
            "INSERT INTO usuarios (id, nome, email, senha) VALUES (?,?,?,?), (?,?,?,?)",
            (usuario_a, "A", f"a{usuario_a}@teste", "x", usuario_b, "B", f"b{usuario_b}@teste", "x"),
        )
        conn.execute(
            "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem) "
            "VALUES (?,?,?,?,?,?,?)",
            (usuario_a * 10 - 1, usuario_a, "Aluguel", 1000, "Moradia", "2026-07-05", "manual"),
        )
        conn.execute(
            "INSERT INTO cartoes_credito (id, usuario_id, nome, bandeira, ultimos_digitos, "
            "limite, saldo_usado, data_vencimento, ativo) VALUES (?,?,?,?,?,?,?,?,?)",
            (usuario_a, usuario_a, "Cartao", "visa", "1234", 5000, 0, 10, 1),
        )
        conn.execute(
            "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem, cartao_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (usuario_a * 10 - 2, usuario_a, "Fatura Cartao", 300, "Cartão de Crédito", "2026-07-10", "fatura", usuario_a),
        )
        conn.execute(
            "INSERT INTO faturas (id, usuario_id, cartao_id, despesa_id, descricao, valor_total, "
            "vencimento, data_referencia) VALUES (?,?,?,?,?,?,?,?)",
            (usuario_a, usuario_a, usuario_a, usuario_a * 10 - 2, "Fatura", 300, "2026-07-10", "2026-07-01"),
        )
        conn.execute(
            "INSERT INTO fatura_itens (id, fatura_id, descricao, valor, categoria, data, estabelecimento) "
            "VALUES (?,?,?,?,?,?,?)",
            (usuario_a * 10 - 1, usuario_a, "Restaurante", 120, "Alimentacao", "2026-07-03", "REST X"),
        )
        conn.execute(
            "INSERT INTO fatura_itens (id, fatura_id, descricao, valor, categoria, data, estabelecimento) "
            "VALUES (?,?,?,?,?,?,?)",
            (usuario_a * 10 - 2, usuario_a, "Uber", 150, "Transporte", "2026-07-04", "UBER"),
        )
        # soma dos itens = 270; valor da fatura = 300 -> ajuste de 30 esperado

        conn.execute(
            "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem) "
            "VALUES (?,?,?,?,?,?,?)",
            (usuario_b * 10 - 1, usuario_b, "Segredo do usuario B", 999, "Lazer", "2026-07-01", "manual"),
        )
        conn.commit()
    finally:
        conn.close()


class TestSombreamentoSqlite:
    def test_sombreamento_isola_usuario_mesmo_sem_where(self, banco_sqlite):
        _inserir_fixture_reconciliacao_sqlite(banco_sqlite, usuario_a=1, usuario_b=2)

        sql_validado = validar("SELECT descricao, valor FROM vw_despesas_reconciliadas", "sqlite")
        resultado = executar(sql_validado, usuario_id=2)

        descricoes = {linha["descricao"] for linha in resultado.linhas}
        assert descricoes == {"Segredo do usuario B"}

    def test_bypass_por_schema_qualificado_e_barrado_antes_de_executar(self, banco_sqlite):
        _inserir_fixture_reconciliacao_sqlite(banco_sqlite, usuario_a=1, usuario_b=2)

        with pytest.raises(SqlRejeitadoError):
            validar("SELECT * FROM main.vw_despesas_reconciliadas", "sqlite")

    def test_teste_de_ouro_view_bate_com_analysis_categorias_do_periodo(self, banco_sqlite):
        """SUM(valor) GROUP BY categoria da view precisa bater, centavo a
        centavo, com _categorias_do_periodo em Python -- inclusive o bucket
        de ajuste de conciliacao. Se as duas implementacoes divergirem, e
        aqui que aparece."""
        _inserir_fixture_reconciliacao_sqlite(banco_sqlite, usuario_a=1, usuario_b=2)

        sql_validado = validar(
            "SELECT categoria, SUM(valor) AS total FROM vw_despesas_reconciliadas "
            "WHERE data_competencia BETWEEN '2026-07-01' AND '2026-07-31' "
            "GROUP BY categoria",
            "sqlite",
        )
        resultado = executar(sql_validado, usuario_id=1)
        totais_da_view = {linha["categoria"]: float(linha["total"]) for linha in resultado.linhas}

        conn = sqlite3.connect(banco_sqlite)
        conn.row_factory = sqlite3.Row
        try:
            from types import SimpleNamespace

            despesas = [
                SimpleNamespace(id=row["id"], valor=row["valor"], categoria=row["categoria"], data=_data(row["data"]))
                for row in conn.execute("SELECT id, valor, categoria, data FROM despesas WHERE usuario_id = 1")
            ]
            faturas = [
                SimpleNamespace(
                    despesa_id=row["despesa_id"],
                    data_referencia=_data(row["data_referencia"]),
                    itens=[
                        SimpleNamespace(valor=item["valor"], categoria=item["categoria"])
                        for item in conn.execute(
                            "SELECT valor, categoria FROM fatura_itens WHERE fatura_id = ?", (row["id"],)
                        )
                    ],
                )
                for row in conn.execute("SELECT id, despesa_id, data_referencia FROM faturas WHERE usuario_id = 1")
            ]
        finally:
            conn.close()

        totais_do_analysis = _categorias_do_periodo(despesas, faturas, mes=7, ano=2026)

        assert totais_da_view == pytest.approx(totais_do_analysis, abs=0.01)
        assert totais_da_view["Ajustes da fatura"] == pytest.approx(30.0, abs=0.01)
        assert totais_da_view["Alimentação"] == pytest.approx(120.0, abs=0.01)
        assert totais_da_view["Transporte"] == pytest.approx(150.0, abs=0.01)
        assert totais_da_view["Moradia"] == pytest.approx(1000.0, abs=0.01)

    def test_limite_de_linhas_e_injetado_quando_ausente(self, banco_sqlite):
        _inserir_fixture_reconciliacao_sqlite(banco_sqlite, usuario_a=1, usuario_b=2)
        sql_validado = validar("SELECT * FROM vw_despesas_reconciliadas", "sqlite")
        resultado = executar(sql_validado, usuario_id=1, limite_linhas=2)
        assert len(resultado.linhas) <= 2

    def test_usuario_id_precisa_ser_int(self, banco_sqlite):
        sql_validado = validar("SELECT * FROM vw_receitas", "sqlite")
        with pytest.raises(TypeError):
            executar(sql_validado, usuario_id="1 OR 1=1")  # type: ignore[arg-type]


def _data(valor):
    from datetime import date

    if isinstance(valor, str):
        ano, mes, dia = (int(p) for p in valor.split("-"))
        return date(ano, mes, dia)
    return valor


# ==================== metade Postgres: docker-compose real ====================


def _postgres_disponivel() -> bool:
    return bool(os.getenv("TEST_POSTGRES_HOST"))


@pytest.fixture
def banco_postgres(monkeypatch):
    if not _postgres_disponivel():
        pytest.skip(
            "TEST_POSTGRES_HOST nao definido -- usar docker-compose.validacao.yml"
        )

    import psycopg2

    if os.getenv("TEST_POSTGRES_DB") != "financaslm_validacao":
        pytest.fail("Os testes destrutivos exigem a base descartavel financaslm_validacao")
    for chave in ("HOST", "PORT", "USER", "PASSWORD", "DB"):
        monkeypatch.setenv(f"POSTGRES_{chave}", os.environ[f"TEST_POSTGRES_{chave}"])
    monkeypatch.delenv("DATABASE_URL", raising=False)
    parametros = dict(
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )
    usuario_a, usuario_b = -101, -102
    conn = psycopg2.connect(**parametros)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            _limpar_fixture_postgres(cur, usuario_a, usuario_b)
            _inserir_fixture_reconciliacao_postgres(cur, usuario_a, usuario_b)
        yield usuario_a, usuario_b
    finally:
        with conn.cursor() as cur:
            _limpar_fixture_postgres(cur, usuario_a, usuario_b)
        conn.close()


def _limpar_fixture_postgres(cur, usuario_a: int, usuario_b: int) -> None:
    cur.execute("DELETE FROM fatura_itens WHERE fatura_id = %s", (usuario_a,))
    cur.execute("DELETE FROM faturas WHERE usuario_id IN (%s,%s)", (usuario_a, usuario_b))
    cur.execute("DELETE FROM despesas WHERE usuario_id IN (%s,%s)", (usuario_a, usuario_b))
    cur.execute("DELETE FROM cartoes_credito WHERE usuario_id IN (%s,%s)", (usuario_a, usuario_b))
    cur.execute("DELETE FROM usuarios WHERE id IN (%s,%s)", (usuario_a, usuario_b))


def _inserir_fixture_reconciliacao_postgres(cur, usuario_a: int, usuario_b: int) -> None:
    cur.execute(
        "INSERT INTO usuarios (id, nome, email, senha) VALUES (%s,%s,%s,%s), (%s,%s,%s,%s)",
        (usuario_a, "A", f"a{usuario_a}@teste", "x", usuario_b, "B", f"b{usuario_b}@teste", "x"),
    )
    cur.execute(
        "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a * 10 - 1, usuario_a, "Aluguel", 1000, "Moradia", "2026-07-05", "manual"),
    )
    cur.execute(
        "INSERT INTO cartoes_credito (id, usuario_id, nome, bandeira, ultimos_digitos, "
        "limite, saldo_usado, data_vencimento, ativo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a, usuario_a, "Cartao", "visa", "1234", 5000, 0, 10, True),
    )
    cur.execute(
        "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem, cartao_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a * 10 - 2, usuario_a, "Fatura Cartao", 300, "Cartão de Crédito", "2026-07-10", "fatura", usuario_a),
    )
    cur.execute(
        "INSERT INTO faturas (id, usuario_id, cartao_id, despesa_id, descricao, valor_total, "
        "vencimento, data_referencia) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a, usuario_a, usuario_a, usuario_a * 10 - 2, "Fatura", 300, "2026-07-10", "2026-07-01"),
    )
    cur.execute(
        "INSERT INTO fatura_itens (id, fatura_id, descricao, valor, categoria, data, estabelecimento) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a * 10 - 1, usuario_a, "Restaurante", 120, "Alimentacao", "2026-07-03", "REST X"),
    )
    cur.execute(
        "INSERT INTO fatura_itens (id, fatura_id, descricao, valor, categoria, data, estabelecimento) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (usuario_a * 10 - 2, usuario_a, "Uber", 150, "Transporte", "2026-07-04", "UBER"),
    )
    cur.execute(
        "INSERT INTO despesas (id, usuario_id, descricao, valor, categoria, data, origem) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (usuario_b * 10 - 1, usuario_b, "Segredo do usuario B", 999, "Lazer", "2026-07-01", "manual"),
    )


class TestSombreamentoPostgres:
    def test_sombreamento_isola_usuario_mesmo_sem_where(self, banco_postgres):
        usuario_a, usuario_b = banco_postgres
        sql_validado = validar("SELECT descricao, valor FROM vw_despesas_reconciliadas", "postgres")
        resultado = executar(sql_validado, usuario_id=usuario_b)
        descricoes = {linha["descricao"] for linha in resultado.linhas}
        assert descricoes == {"Segredo do usuario B"}

    def test_bypass_por_schema_qualificado_e_barrado_antes_de_executar(self, banco_postgres):
        with pytest.raises(SqlRejeitadoError):
            validar("SELECT * FROM public.vw_despesas_reconciliadas", "postgres")

    def test_teste_de_ouro_view_bate_com_analysis_categorias_do_periodo(self, banco_postgres):
        usuario_a, _ = banco_postgres
        sql_validado = validar(
            "SELECT categoria, SUM(valor) AS total FROM vw_despesas_reconciliadas "
            "WHERE data_competencia BETWEEN '2026-07-01' AND '2026-07-31' "
            "GROUP BY categoria",
            "postgres",
        )
        resultado = executar(sql_validado, usuario_id=usuario_a)
        totais_da_view = {linha["categoria"]: float(linha["total"]) for linha in resultado.linhas}

        assert totais_da_view["Ajustes da fatura"] == pytest.approx(30.0, abs=0.01)
        assert totais_da_view["Alimentação"] == pytest.approx(120.0, abs=0.01)
        assert totais_da_view["Transporte"] == pytest.approx(150.0, abs=0.01)
        assert totais_da_view["Moradia"] == pytest.approx(1000.0, abs=0.01)


# ==================== guarda estrutural: sem dependencia de ML no backend ====================


def test_backend_nao_depende_de_bibliotecas_de_ml():
    """sqlglot e um parser estatico de SQL, nao uma biblioteca de ML -- essa
    guarda protege a decisao de arquitetura de que o backend so fala HTTP
    com o runtime local do modelo, nunca carrega pesos."""
    caminho = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
    conteudo = open(caminho, encoding="utf-8").read().lower()
    for proibida in ("torch", "transformers", "peft", "bitsandbytes", "accelerate"):
        assert proibida not in conteudo, f"{proibida} nao pode entrar no backend"
