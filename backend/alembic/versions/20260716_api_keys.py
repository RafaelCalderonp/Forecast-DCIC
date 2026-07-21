"""api_keys: tabla para autenticación M2M (panel 90 días)

Revision ID: 20260716_api_keys
Revises: 20260715_idempotencia
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = '20260716_api_keys'
down_revision = '20260715_idempotencia'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='TRUE'),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ultimo_uso', sa.DateTime(timezone=True), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])


def downgrade() -> None:
    op.drop_index('ix_api_keys_key_hash', 'api_keys')
    op.drop_table('api_keys')
