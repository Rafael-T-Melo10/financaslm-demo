"""Validador estatico do SQL gerado pelo modelo, antes de qualquer execucao.

Camada complementar ao sombreamento de views por usuario (execucao_sql.py):
poc_sombreamento_view.py (backend/scripts/) provou que o sombreamento por
CREATE TEMP VIEW NAO protege contra nomes qualificados por schema
(main.<view> / public.<view>) -- por isso este validador rejeita esse padrao
explicitamente, alem de qualquer coisa que nao seja uma unica consulta de
leitura sobre a allowlist de views reconciliadas criadas pela migracao
d1a9b7e4f2c6_views_reconciliadas_assistente.

Nao e uma dependencia de ML: sqlglot e um parser estatico de SQL em Python
puro (ver nota em backend/requirements.txt) -- nao carrega nenhum modelo.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

VIEWS_PERMITIDAS = frozenset({
    "vw_despesas_reconciliadas",
    "vw_receitas",
    "vw_cartoes",
    "vw_parcelas",
    "vw_despesas_recorrentes",
})

_TABELAS_CRUAS = frozenset({
    "usuarios", "familias", "membros_familia", "categorias", "regras_classificacao",
    "receitas", "receita_itens", "despesas", "cartoes_credito", "faturas",
    "fatura_itens", "parcelas", "despesas_recorrentes", "configuracoes",
    "senhas_pdf", "notificacoes", "gmail_conexoes", "importacoes_pendentes",
})

NOMES_RESERVADOS = VIEWS_PERMITIDAS | _TABELAS_CRUAS
"""Nomes que um alias de CTE nunca pode reutilizar.

Sem essa checagem, uma CTE nao-recursiva chamada "despesas" cujo corpo
tambem referencia "despesas" e sintaticamente indistinguivel, so pelo nome,
de uma referencia legitima a propria CTE -- mas semanticamente resolve para
a TABELA CRUA (regra padrao de SQL: um WITH nao-recursivo nao enxerga a si
mesmo). Rejeitar a colisao de nome fecha essa ambiguidade sem precisar
rastrear escopo/posicao no AST.
"""

_FUNCOES_PROIBIDAS = frozenset({
    "load_extension", "pg_sleep", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "dblink", "dblink_connect", "lo_import", "lo_export",
    "setval", "nextval", "currval",
})
"""Bloqueio por nome, em defesa de profundidade -- a allowlist de views ja
impede o acesso a dado fora do escopo do usuario; isto cobre funcoes que nao
tocam tabela nenhuma (ex. pg_sleep) ou que expoem o sistema de arquivos/
sessao do servidor, que o allowlist de views nao alcança."""


class SqlRejeitadoError(ValueError):
    """SQL gerado pelo modelo nao passou no validador estatico.

    Nunca chega a execucao_sql.py -- vira veredito="nao_sei" tecnico em
    servico.py, com metrica propria no harness de avaliacao (distinto do
    modelo dizer "nao sei": aqui e o validador dizendo que a consulta nem
    pode tentar rodar).
    """


@dataclass(frozen=True)
class SqlValidado:
    sql: str
    dialeto: str
    views_referenciadas: frozenset[str]
    arvore: exp.Expression
    """AST ja parseada -- execucao_sql.py reusa para injetar LIMIT sem reparsear."""


def validar(sql: str, dialeto: str) -> SqlValidado:
    """Levanta SqlRejeitadoError na primeira violacao. Nunca reescreve o SQL."""
    sql = (sql or "").strip()
    if not sql:
        raise SqlRejeitadoError("consulta vazia")

    try:
        statements = [s for s in sqlglot.parse(sql, read=dialeto) if s is not None]
    except (ParseError, TokenError) as exc:
        raise SqlRejeitadoError(f"SQL invalido: {exc}") from exc

    if len(statements) != 1:
        raise SqlRejeitadoError(
            f"esperada exatamente uma instrucao, recebidas {len(statements)}"
        )

    raiz = statements[0]
    if not isinstance(raiz, exp.Query):
        raise SqlRejeitadoError(
            "apenas consultas de leitura (SELECT, WITH ou UNION) sao permitidas, "
            f"recebido {type(raiz).__name__}"
        )

    _rejeitar_funcoes_proibidas(raiz)
    _rejeitar_alias_de_cte_reservado(raiz)
    views = _extrair_e_validar_tabelas(raiz)

    return SqlValidado(sql=sql, dialeto=dialeto, views_referenciadas=frozenset(views), arvore=raiz)


def _nome_funcao(func: exp.Func) -> str:
    if isinstance(func, exp.Anonymous):
        return str(func.this or "").lower()
    return (func.sql_name() or "").lower()


def _rejeitar_funcoes_proibidas(raiz: exp.Expression) -> None:
    for func in raiz.find_all(exp.Func):
        nome = _nome_funcao(func)
        if nome in _FUNCOES_PROIBIDAS:
            raise SqlRejeitadoError(f"funcao proibida: {nome}")


def _rejeitar_alias_de_cte_reservado(raiz: exp.Expression) -> None:
    for cte in raiz.find_all(exp.CTE):
        alias = cte.alias_or_name.lower()
        if alias in NOMES_RESERVADOS:
            raise SqlRejeitadoError(
                f"nome de CTE '{alias}' reutiliza um nome de tabela ou view reservado -- "
                "nao permitido (evita ambiguidade de escopo entre a CTE e a tabela real)"
            )


def _extrair_e_validar_tabelas(raiz: exp.Expression) -> set[str]:
    nomes_cte = {cte.alias_or_name.lower() for cte in raiz.find_all(exp.CTE)}

    views: set[str] = set()
    for tabela in raiz.find_all(exp.Table):
        nome = (tabela.name or "").lower()
        if not nome:
            raise SqlRejeitadoError(
                "referencia de tabela sem nome (provavel funcao usada como fonte de linhas)"
            )
        if nome in nomes_cte:
            continue

        schema = tabela.db or tabela.args.get("catalog")
        if schema:
            raise SqlRejeitadoError(
                f"referencia qualificada por schema nao permitida: {schema}.{tabela.name} -- "
                "bypass do sombreamento por usuario (ver poc_sombreamento_view.py)"
            )

        if nome not in VIEWS_PERMITIDAS:
            raise SqlRejeitadoError(
                f"tabela ou view '{tabela.name}' fora da allowlist; apenas "
                f"{sorted(VIEWS_PERMITIDAS)} sao permitidas"
            )
        views.add(nome)

    return views
