"""criar senhas pdf por usuario

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-07-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "senhas_pdf",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("instituicao", sa.String(length=30), nullable=False),
        sa.Column("valor_criptografado", sa.Text(), nullable=False),
        sa.Column("data_atualizacao", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("usuario_id", "instituicao", name="uq_senha_pdf_usuario_instituicao"),
    )


def downgrade() -> None:
    op.drop_table("senhas_pdf")
