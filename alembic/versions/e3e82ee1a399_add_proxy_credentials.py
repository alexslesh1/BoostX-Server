"""add proxy_credentials

Revision ID: e3e82ee1a399
Revises: d06cc3403990
Create Date: 2026-07-12 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3e82ee1a399'
down_revision: Union[str, None] = 'd06cc3403990'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('proxy_credentials',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('proxy_login', sa.String(length=64), nullable=False),
    sa.Column('password_encrypted', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_proxy_credentials_proxy_login'), 'proxy_credentials', ['proxy_login'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_proxy_credentials_proxy_login'), table_name='proxy_credentials')
    op.drop_table('proxy_credentials')
