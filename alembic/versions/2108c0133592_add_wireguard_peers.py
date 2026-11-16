"""add wireguard_peers

Revision ID: 2108c0133592
Revises: e3e82ee1a399
Create Date: 2026-07-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2108c0133592'
down_revision: Union[str, None] = 'e3e82ee1a399'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('wireguard_peers',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('public_key', sa.String(length=64), nullable=False),
    sa.Column('private_key_encrypted', sa.String(length=512), nullable=False),
    sa.Column('assigned_ip', sa.String(length=15), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id'),
    sa.UniqueConstraint('assigned_ip')
    )
    op.create_index(op.f('ix_wireguard_peers_assigned_ip'), 'wireguard_peers', ['assigned_ip'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_wireguard_peers_assigned_ip'), table_name='wireguard_peers')
    op.drop_table('wireguard_peers')
