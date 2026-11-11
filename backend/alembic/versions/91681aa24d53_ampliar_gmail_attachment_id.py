"""ampliar gmail_attachment_id para text

Revision ID: 91681aa24d53
Revises: c6e4f40843d6
Create Date: 2026-07-10 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91681aa24d53'
down_revision: Union[str, None] = 'c6e4f40843d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.alter_column(
            'gmail_attachment_id',
            existing_type=sa.String(length=200),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('importacoes_pendentes', schema=None) as batch_op:
        batch_op.alter_column(
            'gmail_attachment_id',
            existing_type=sa.Text(),
            type_=sa.String(length=200),
            existing_nullable=False,
        )
