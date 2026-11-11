"""views reconciliadas para o assistente text2sql

Revision ID: d1a9b7e4f2c6
Revises: f0468fef4ba5
Create Date: 2026-08-05 00:00:00.000000

Cria views somente-leitura, schema-only (nenhuma tabela e alterada), que o
assistente text2SQL usa como unica superficie de consulta permitida:

- vw_despesas_reconciliadas: replica a logica de reconciliacao de
  analysis._categorias_do_periodo (backend/app/services/analysis.py) -- quando
  uma despesa e o resumo de uma fatura com itens, a despesa-resumo e excluida
  e os itens entram no lugar dela, com o residuo em "Ajustes da fatura". Sem
  isso, somar despesas + fatura_itens conta o mesmo gasto duas vezes.
- vw_receitas, vw_cartoes, vw_parcelas, vw_despesas_recorrentes: pass-through
  direto das tabelas correspondentes.

Escopo deliberadamente NAO inclui uma "vw_compromissos" projetando parcelas e
recorrencias para os proximos meses: essa expansao e procedural em Python
(_compromissos_de_parcelas / _compromissos_de_recorrencias, com loop mes a
mes) e nao tem uma traducao simples e portavel entre SQLite e Postgres (o
Postgres tem generate_series, o SQLite nao). Perguntas sobre compromissos
futuros consultam vw_parcelas / vw_despesas_recorrentes diretamente; uma
projecao completa fica como possivel extensao futura (CTE recursiva).

Nenhuma view contem filtro de usuario_id embutido -- o isolamento por usuario
e feito em tempo de execucao por execucao_sql.py, via views temporarias que
sombreiam estas (ver backend/scripts/poc_sombreamento_view.py, que provou o
mecanismo em SQLite e Postgres).

IMPORTANTE: o SQL das views vive em app/services/assistente/ddl_views.py, nao
aqui -- e a mesma fonte que backend/tests/test_assistente_seguranca.py usa
para montar o banco de teste. Duas copias do mesmo SQL divergiriam
silenciosamente com o tempo; uma unica fonte nao pode.
"""
import os
import sys
from typing import Sequence, Union

from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.services.assistente.ddl_views import VIEWS  # noqa: E402


# revision identifiers, used by Alembic.
revision: str = 'd1a9b7e4f2c6'
down_revision: Union[str, None] = 'f0468fef4ba5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for _, sql in VIEWS:
        op.execute(sql)


def downgrade() -> None:
    for nome, _ in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {nome}")
