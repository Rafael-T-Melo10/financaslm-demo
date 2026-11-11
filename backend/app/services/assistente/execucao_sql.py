"""Execucao do SQL ja validado, isolada por usuario via sombreamento de view.

Mecanismo provado experimentalmente em backend/scripts/poc_sombreamento_view.py,
nos dois motores que o projeto suporta (SQLite em dev, Postgres em producao --
selecionado pela mesma variavel POSTGRES_HOST que app/database.py usa):

1. Abre uma conexao dedicada, fora da Session do ORM usada pelo resto do app.
2. Cria, nessa conexao, uma CREATE TEMP VIEW com o MESMO nome de cada view
   permanente da allowlist, ja filtrada por usuario_id. A view temporaria
   sombreia a permanente para qualquer referencia nao qualificada por schema
   -- entao mesmo que o SQL gerado pelo modelo esqueca o WHERE usuario_id, ele
   bate na versao ja filtrada. A referencia interna precisa ser qualificada
   (main.<view> / public.<view>): sem isso a view temp se autorreferencia
   ("circularly defined" no SQLite), porque o nome e resolvido em tempo de
   CONSULTA, nao de criacao.
3. So DEPOIS de criar as views temp, a conexao trava em somente-leitura
   (PRAGMA query_only=ON no SQLite; SET TRANSACTION READ ONLY via
   set_session(readonly=True) no Postgres) -- nessa ordem, porque o Postgres
   rejeita CREATE TEMP VIEW dentro de uma transacao ja somente-leitura
   (confirmado no PoC).
4. Bypass por nome qualificado por schema (main./public.) NAO e bloqueado por
   este mecanismo -- e por isso que validador.py rejeita esse padrao antes de
   qualquer SQL chegar aqui. As duas camadas sao obrigatorias juntas.

Nunca interpola texto do usuario nesta camada: usuario_id e sempre um int
vindo de get_current_user (nunca do modelo ou da pergunta em texto livre).
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from app.services.assistente.validador import VIEWS_PERMITIDAS, SqlValidado

_QUALIFICADOR_POR_MOTOR = {"sqlite": "main", "postgres": "public"}


class ExecucaoSqlError(RuntimeError):
    """A consulta ja validada falhou ao rodar (timeout, erro de execucao)."""


@dataclass(frozen=True)
class ResultadoSql:
    colunas: list[str]
    linhas: list[dict[str, Any]]
    truncado: bool
    tempo_ms: int
    dialeto: str


def motor_atual() -> str:
    """'postgres' ou 'sqlite' -- mesma logica de selecao de app/database.py."""
    return "postgres" if os.getenv("POSTGRES_HOST") else "sqlite"


def _abrir_conexao_bruta(motor: str):
    if motor == "postgres":
        import psycopg2

        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            dbname=os.getenv("POSTGRES_DB"),
        )

    caminho = os.getenv("DATABASE_URL", "sqlite:///./gastos.db").removeprefix("sqlite:///")
    return sqlite3.connect(caminho, timeout=5.0)


def _criar_views_sombreadas_sqlite(conn: sqlite3.Connection, usuario_id: int) -> None:
    qualificador = _QUALIFICADOR_POR_MOTOR["sqlite"]
    for nome in VIEWS_PERMITIDAS:
        conn.execute(
            f"CREATE TEMP VIEW {nome} AS "
            f"SELECT * FROM {qualificador}.{nome} WHERE usuario_id = {int(usuario_id)}"
        )


def _criar_views_sombreadas_postgres(conn, usuario_id: int, timeout_ms: int) -> None:
    qualificador = _QUALIFICADOR_POR_MOTOR["postgres"]
    with conn.cursor() as cur:
        for nome in VIEWS_PERMITIDAS:
            cur.execute(
                f"CREATE TEMP VIEW {nome} AS "
                f"SELECT * FROM {qualificador}.{nome} WHERE usuario_id = {int(usuario_id)}"
            )
        cur.execute(f"SET statement_timeout = {int(timeout_ms)}")


def _instalar_timeout_sqlite(conn: sqlite3.Connection, timeout_s: float) -> None:
    """SQLite nao tem statement_timeout nativo -- aborta a consulta se o
    tempo total de parede exceder timeout_s, verificado a cada 1000 passos
    da VM interna do SQLite."""
    inicio = time.monotonic()

    def _checar() -> int:
        return 1 if (time.monotonic() - inicio) > timeout_s else 0

    conn.set_progress_handler(_checar, 1000)


def _com_limite(sql_validado: SqlValidado, limite_linhas: int) -> str:
    arvore = sql_validado.arvore
    if arvore.args.get("limit"):
        return arvore.sql(dialect=sql_validado.dialeto)
    return arvore.limit(limite_linhas).sql(dialect=sql_validado.dialeto)


def executar(
    sql_validado: SqlValidado,
    usuario_id: int,
    *,
    limite_linhas: int = 500,
    timeout_s: float = 5.0,
) -> ResultadoSql:
    """Executa um SqlValidado (ja passou por validador.validar) isolado por
    usuario. Levanta ExecucaoSqlError se a consulta falhar ou estourar o
    timeout -- nunca deixa uma excecao de driver crua vazar para o chamador.
    """
    if not isinstance(usuario_id, int) or isinstance(usuario_id, bool):
        raise TypeError("usuario_id precisa ser int -- nunca interpole texto aqui")

    motor = motor_atual()
    if motor != sql_validado.dialeto:
        raise RuntimeError(
            f"SQL validado para o dialeto '{sql_validado.dialeto}' mas o motor em "
            f"execucao e '{motor}' -- descompasso entre validador.py e execucao_sql.py"
        )

    sql_final = _com_limite(sql_validado, limite_linhas)
    conn = _abrir_conexao_bruta(motor)
    try:
        inicio = time.monotonic()
        if motor == "sqlite":
            _criar_views_sombreadas_sqlite(conn, usuario_id)
            conn.execute("PRAGMA query_only = ON")
            _instalar_timeout_sqlite(conn, timeout_s)
            try:
                cursor = conn.execute(sql_final)
                colunas = [d[0] for d in cursor.description] if cursor.description else []
                linhas_brutas = cursor.fetchall()
            except sqlite3.OperationalError as exc:
                raise ExecucaoSqlError(f"falha ao executar a consulta: {exc}") from exc
        else:
            import psycopg2

            conn.autocommit = True
            _criar_views_sombreadas_postgres(conn, usuario_id, int(timeout_s * 1000))
            conn.autocommit = False
            conn.set_session(readonly=True)
            try:
                with conn.cursor() as cur:
                    cur.execute(sql_final)
                    colunas = [d.name for d in cur.description] if cur.description else []
                    linhas_brutas = cur.fetchall()
                conn.rollback()
            except psycopg2.Error as exc:
                conn.rollback()
                raise ExecucaoSqlError(f"falha ao executar a consulta: {exc}") from exc

        tempo_ms = int((time.monotonic() - inicio) * 1000)
        linhas = [dict(zip(colunas, linha)) for linha in linhas_brutas]
        return ResultadoSql(
            colunas=colunas,
            linhas=linhas,
            truncado=len(linhas) >= limite_linhas,
            tempo_ms=tempo_ms,
            dialeto=motor,
        )
    finally:
        conn.close()
