"""criar familias e membros

Revision ID: a2b3c4d5e6f7
Revises: f1c9a6b2d4e8
Create Date: 2026-07-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1c9a6b2d4e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "familias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "membros_familia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("familia_id", sa.Integer(), sa.ForeignKey("familias.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("papel", sa.String(length=20), nullable=False, server_default="membro"),
        sa.Column("data_entrada", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("familia_id", "usuario_id", name="uq_membro_familia_usuario"),
        sa.UniqueConstraint("usuario_id", name="uq_usuario_em_uma_familia"),
    )


def downgrade() -> None:
    op.drop_table("membros_familia")
    op.drop_table("familias")
