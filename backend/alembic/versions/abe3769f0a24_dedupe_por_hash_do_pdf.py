"""dedupe de importacao pendente por hash do conteudo do pdf

Revision ID: abe3769f0a24
Revises: 91681aa24d53
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abe3769f0a24'
down_revision: Union[str, None] = '91681aa24d53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hash_anexo', sa.String(length=64), nullable=False, server_default=''))
        batch_op.drop_constraint('uq_importacao_pendente_usuario_mensagem_anexo', type_='unique')
        batch_op.create_unique_constraint(
            'uq_importacao_pendente_usuario_mensagem_hash',
            ['usuario_id', 'gmail_message_id', 'hash_anexo'],
        )


def downgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_importacao_pendente_usuario_mensagem_hash', type_='unique')
        batch_op.create_unique_constraint(
            'uq_importacao_pendente_usuario_mensagem_anexo',
            ['usuario_id', 'gmail_message_id', 'gmail_attachment_id'],
        )
        batch_op.drop_column('hash_anexo')
