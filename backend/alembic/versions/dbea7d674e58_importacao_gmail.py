"""importacao automatica via gmail

Revision ID: dbea7d674e58
Revises: 7b3f7c2d51e4
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbea7d674e58'
down_revision: Union[str, None] = '7b3f7c2d51e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('gmail_conexoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('email_conectado', sa.String(length=255), nullable=False),
    sa.Column('refresh_token', sa.Text(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('ultima_sincronizacao', sa.DateTime(), nullable=True),
    sa.Column('ultimo_erro', sa.Text(), nullable=True),
    sa.Column('data_criacao', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id')
    )

    op.create_table('importacoes_pendentes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('gmail_message_id', sa.String(length=100), nullable=False),
    sa.Column('remetente', sa.String(length=255), nullable=False),
    sa.Column('assunto', sa.String(length=500), nullable=True),
    sa.Column('data_recebimento', sa.DateTime(), nullable=True),
    sa.Column('tipo_detectado', sa.String(length=20), nullable=False),
    sa.Column('cartao_id_sugerido', sa.Integer(), nullable=True),
    sa.Column('dados_extraidos_json', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('mensagem_erro', sa.Text(), nullable=True),
    sa.Column('data_criacao', sa.DateTime(), nullable=True),
    sa.Column('data_revisao', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['cartao_id_sugerido'], ['cartoes_credito.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'gmail_message_id', name='uq_importacao_pendente_usuario_mensagem')
    )


def downgrade() -> None:
    op.drop_table('importacoes_pendentes')
    op.drop_table('gmail_conexoes')
