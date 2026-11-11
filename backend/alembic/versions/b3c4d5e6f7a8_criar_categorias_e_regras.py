"""criar categorias e regras de classificacao

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-18 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("cor", sa.String(length=7), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sistema", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id", "nome", name="uq_categoria_usuario_nome"),
    )
    op.create_table(
        "regras_classificacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("palavra_chave", sa.String(length=255), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=False),
        sa.Column("prioridade", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id", "palavra_chave", name="uq_regra_usuario_palavra"),
    )


def downgrade() -> None:
    op.drop_table("regras_classificacao")
    op.drop_table("categorias")
