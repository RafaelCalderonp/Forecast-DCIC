"""ajuste_precio_2026: corrección de forecast por alza de precios (panel expertos ago-2026)

Revision ID: 20260813_ajuste_precio
Revises: 20260812_quiebres
Create Date: 2026-08-13

Panel (Meller/Torres/Larraín): tratar el alza de precios reciente igual que el
quiebre de stock 2025 — una capa de corrección aparte, auditable, sin tocar
los hiperparámetros de Holt-Winters. factor_ajuste se aplica sobre
forecast_ajustado (Capa 2→3) como piso conservador, no como elasticidad fina
por SKU (muy poca data real para eso — solo ~1 mes post-alza).
"""
from alembic import op
import sqlalchemy as sa

revision = '20260813_ajuste_precio'
down_revision = '20260812_quiebres'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ajuste_precio_2026',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku', sa.String(50), nullable=False),
        sa.Column('precio_anterior', sa.Numeric(12, 2), nullable=False),
        sa.Column('precio_nuevo', sa.Numeric(12, 2), nullable=False),
        sa.Column('delta_pct', sa.Numeric(6, 2), nullable=False),
        sa.Column('factor_ajuste', sa.Numeric(5, 3), nullable=False),
        sa.Column('fecha_deteccion', sa.Date(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='TRUE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('sku', name='uq_ajuste_precio_sku'),
    )
    op.create_index('ix_ajuste_precio_sku', 'ajuste_precio_2026', ['sku'])


def downgrade() -> None:
    op.drop_index('ix_ajuste_precio_sku', 'ajuste_precio_2026')
    op.drop_table('ajuste_precio_2026')
