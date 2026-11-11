"""central de notificacoes persistentes

Revision ID: e8d4f2a71c90
Revises: bc3bc6d7d6e6
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8d4f2a71c90"
down_revision: Union[str, None] = "bc3bc6d7d6e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("severidade", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="ativa"),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("rota", sa.String(length=255), nullable=True),
        sa.Column("progresso_atual", sa.Integer(), nullable=True),
        sa.Column("progresso_total", sa.Integer(), nullable=True),
        sa.Column("lida_em", sa.DateTime(), nullable=True),
        sa.Column("resolvida_em", sa.DateTime(), nullable=True),
        sa.Column("criada_em", sa.DateTime(), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "chave", name="uq_notificacao_usuario_chave"),
    )


def downgrade() -> None:
    op.drop_table("notificacoes")
