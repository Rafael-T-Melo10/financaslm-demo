"""Definicao das views somente-leitura que o assistente text2SQL consulta.

Fonte unica de verdade: a migracao Alembic
(d1a9b7e4f2c6_views_reconciliadas_assistente) e a suite de testes
(test_assistente_seguranca.py) importam VIEWS daqui, em vez de cada uma ter
sua propria copia do SQL. Isso existe especificamente para que o "teste de
ouro" (esta view x analysis._categorias_do_periodo) continue comparando a
MESMA definicao que esta de fato aplicada em producao -- duas copias do
mesmo SQL podem divergir silenciosamente com o tempo, uma unica nao pode.

SQL padrao (CASE, JOIN, UNION ALL, NOT EXISTS), sem nada especifico de motor
-- roda identico em SQLite e Postgres, os dois motores que o projeto suporta
(selecao por POSTGRES_HOST, ver app/database.py).
"""

# Espelha CATEGORIAS_DASHBOARD (backend/app/services/analysis.py) -- inclui as
# variantes acentuada e sem-acento porque classificar_categoria (parser.py)
# emite as duas.
_CASE_CATEGORIA = """
    CASE LOWER({coluna})
        WHEN 'alimentacao' THEN 'Alimentação'
        WHEN 'alimentação' THEN 'Alimentação'
        WHEN 'transporte' THEN 'Transporte'
        WHEN 'saude' THEN 'Saúde'
        WHEN 'saúde' THEN 'Saúde'
        WHEN 'educacao' THEN 'Educação'
        WHEN 'educação' THEN 'Educação'
        WHEN 'lazer' THEN 'Lazer'
        WHEN 'diversao' THEN 'Lazer'
        WHEN 'diversão' THEN 'Lazer'
        WHEN 'moradia' THEN 'Moradia'
        WHEN 'assinaturas' THEN 'Assinaturas'
        WHEN 'roupas' THEN 'Roupas'
        WHEN 'vestuario' THEN 'Roupas'
        WHEN 'vestuário' THEN 'Roupas'
        WHEN 'impostos' THEN 'Impostos'
        WHEN 'cartao de credito' THEN 'Cartão de Crédito'
        WHEN 'cartão de crédito' THEN 'Cartão de Crédito'
        WHEN 'ajustes' THEN 'Ajustes da fatura'
        WHEN 'ajustes da fatura' THEN 'Ajustes da fatura'
        WHEN 'outros' THEN 'Outros'
        ELSE {coluna}
    END
"""

VW_DESPESAS_RECONCILIADAS = f"""
CREATE VIEW vw_despesas_reconciliadas AS
SELECT
    d.usuario_id AS usuario_id,
    d.id AS despesa_id,
    NULL AS fatura_item_id,
    d.descricao AS descricao,
    NULL AS estabelecimento,
    d.valor AS valor,
    {_CASE_CATEGORIA.format(coluna='d.categoria')} AS categoria,
    d.data AS data_competencia,
    d.data AS data_transacao,
    d.origem AS origem,
    'despesa' AS grao,
    0 AS eh_ajuste
FROM despesas d
WHERE NOT EXISTS (
    SELECT 1 FROM faturas f
    JOIN fatura_itens fi ON fi.fatura_id = f.id
    WHERE f.despesa_id = d.id
)

UNION ALL

SELECT
    d.usuario_id AS usuario_id,
    d.id AS despesa_id,
    fi.id AS fatura_item_id,
    fi.descricao AS descricao,
    fi.estabelecimento AS estabelecimento,
    fi.valor AS valor,
    {_CASE_CATEGORIA.format(coluna='fi.categoria')} AS categoria,
    f.data_referencia AS data_competencia,
    fi.data AS data_transacao,
    d.origem AS origem,
    'item_fatura' AS grao,
    0 AS eh_ajuste
FROM fatura_itens fi
JOIN faturas f ON f.id = fi.fatura_id
JOIN despesas d ON d.id = f.despesa_id

UNION ALL

SELECT
    d.usuario_id AS usuario_id,
    d.id AS despesa_id,
    NULL AS fatura_item_id,
    'Ajustes da fatura' AS descricao,
    NULL AS estabelecimento,
    (d.valor - soma.total_itens) AS valor,
    'Ajustes da fatura' AS categoria,
    f.data_referencia AS data_competencia,
    f.data_referencia AS data_transacao,
    d.origem AS origem,
    'ajuste' AS grao,
    1 AS eh_ajuste
FROM faturas f
JOIN despesas d ON d.id = f.despesa_id
JOIN (
    SELECT fatura_id, SUM(valor) AS total_itens
    FROM fatura_itens
    GROUP BY fatura_id
) soma ON soma.fatura_id = f.id
WHERE ABS(d.valor - soma.total_itens) >= 0.01
"""

VW_RECEITAS = """
CREATE VIEW vw_receitas AS
SELECT
    id AS receita_id,
    usuario_id,
    descricao,
    valor,
    data,
    origem
FROM receitas
"""

VW_CARTOES = """
CREATE VIEW vw_cartoes AS
SELECT
    id AS cartao_id,
    usuario_id,
    nome,
    bandeira,
    ultimos_digitos,
    limite,
    saldo_usado,
    data_vencimento,
    ativo
FROM cartoes_credito
"""

VW_PARCELAS = """
CREATE VIEW vw_parcelas AS
SELECT
    id AS parcela_id,
    usuario_id,
    cartao_id,
    descricao,
    valor_total,
    parcelas_restantes,
    total_parcelas,
    valor_parcela,
    data_inicio,
    data_proxima_parcela,
    pago
FROM parcelas
"""

VW_DESPESAS_RECORRENTES = """
CREATE VIEW vw_despesas_recorrentes AS
SELECT
    id AS recorrente_id,
    usuario_id,
    cartao_id,
    descricao,
    valor,
    categoria,
    dia_vencimento,
    ativo,
    data_inicio,
    ultima_geracao
FROM despesas_recorrentes
"""

VIEWS: tuple[tuple[str, str], ...] = (
    ("vw_despesas_reconciliadas", VW_DESPESAS_RECONCILIADAS),
    ("vw_receitas", VW_RECEITAS),
    ("vw_cartoes", VW_CARTOES),
    ("vw_parcelas", VW_PARCELAS),
    ("vw_despesas_recorrentes", VW_DESPESAS_RECORRENTES),
)


def criar_views(conexao) -> None:
    """Executa os 5 CREATE VIEW numa conexao DB-API crua (sqlite3 ou
    psycopg2) ou via SQLAlchemy Connection/op.execute -- qualquer objeto com
    .execute(sql)."""
    for _, sql in VIEWS:
        conexao.execute(sql)


def dropar_views(conexao) -> None:
    for nome, _ in reversed(VIEWS):
        conexao.execute(f"DROP VIEW IF EXISTS {nome}")
