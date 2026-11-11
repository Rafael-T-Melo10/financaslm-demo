"""corrigir competencia de contas de consumo legadas

Revision ID: f1c9a6b2d4e8
Revises: e8d4f2a71c90
Create Date: 2026-07-14 00:30:00.000000

"""
from datetime import date
import json
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1c9a6b2d4e8"
down_revision: Union[str, None] = "e8d4f2a71c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


despesas = sa.table(
    "despesas",
    sa.column("id", sa.Integer()),
    sa.column("descricao", sa.String()),
    sa.column("data", sa.Date()),
    sa.column("origem", sa.String()),
)

importacoes_pendentes = sa.table(
    "importacoes_pendentes",
    sa.column("id", sa.Integer()),
    sa.column("tipo_detectado", sa.String()),
    sa.column("status", sa.String()),
    sa.column("dados_extraidos_json", sa.Text()),
)

MESES = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4,
    "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8,
    "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}


def _competencia_descricao(descricao: str | None) -> date | None:
    match = re.search(
        r"\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)/(\d{4})\b",
        descricao or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    return date(int(match.group(2)), MESES[match.group(1).upper()], 1)


def recalcular_competencia_contas(bind) -> None:
    registros = bind.execute(
        sa.select(despesas.c.id, despesas.c.descricao, despesas.c.data)
        .where(despesas.c.origem == "conta")
    ).mappings().all()

    for registro in registros:
        competencia = _competencia_descricao(registro["descricao"])
        if not competencia or registro["data"] == competencia:
            continue
        bind.execute(
            sa.update(despesas)
            .where(despesas.c.id == registro["id"])
            .values(data=competencia)
        )

    pendencias = bind.execute(
        sa.select(
            importacoes_pendentes.c.id,
            importacoes_pendentes.c.dados_extraidos_json,
        ).where(
            importacoes_pendentes.c.tipo_detectado == "conta",
            importacoes_pendentes.c.status.in_(("pendente", "erro")),
        )
    ).mappings().all()

    for pendencia in pendencias:
        try:
            dados = json.loads(pendencia["dados_extraidos_json"] or "{}")
        except (TypeError, ValueError):
            continue
        competencia = _competencia_descricao(
            (dados.get("informacoes_conta") or {}).get("referencia")
        )
        if not competencia:
            continue

        alterado = False
        for despesa in dados.get("despesas", []):
            if despesa.get("data") != competencia.isoformat():
                despesa["data"] = competencia.isoformat()
                alterado = True
        if alterado:
            bind.execute(
                sa.update(importacoes_pendentes)
                .where(importacoes_pendentes.c.id == pendencia["id"])
                .values(dados_extraidos_json=json.dumps(dados, ensure_ascii=False))
            )


def upgrade() -> None:
    recalcular_competencia_contas(op.get_bind())


def downgrade() -> None:
    # Migração de reparo: a data de vencimento anterior não pode ser reconstruída com segurança.
    pass
