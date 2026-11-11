"""dedupe de importacao pendente por anexo do gmail

Revision ID: c6e4f40843d6
Revises: dbea7d674e58
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6e4f40843d6'
down_revision: Union[str, None] = 'dbea7d674e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gmail_attachment_id', sa.String(length=200), nullable=False, server_default=''))
        batch_op.drop_constraint('uq_importacao_pendente_usuario_mensagem', type_='unique')
        batch_op.create_unique_constraint(
            'uq_importacao_pendente_usuario_mensagem_anexo',
            ['usuario_id', 'gmail_message_id', 'gmail_attachment_id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_importacao_pendente_usuario_mensagem_anexo', type_='unique')
        batch_op.create_unique_constraint(
            'uq_importacao_pendente_usuario_mensagem',
            ['usuario_id', 'gmail_message_id'],
        )
        batch_op.drop_column('gmail_attachment_id')
