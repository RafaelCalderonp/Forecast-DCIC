"""quiebres_stock_2025: demanda corregida por quiebres de stock detectados en 2025

Revision ID: 20260812_quiebres
Revises: 20260716_api_keys
Create Date: 2026-08-12

Corrige el forecast: en meses con quiebre de stock, la venta real registrada
subestima la demanda real (no se vendió porque no había stock, no porque no
había demanda). Esta tabla guarda la demanda base corregida por SKU/mes,
usada por ForecastService para ajustar la serie histórica antes de calibrar
Holt-Winters — sin modificar los registros reales de la tabla ventas.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260812_quiebres'
down_revision = '20260716_api_keys'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quiebres_stock_2025',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku', sa.String(50), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('dias_quiebre', sa.Integer(), nullable=True),
        sa.Column('pct_mes_quiebre', sa.Numeric(5, 2), nullable=True),
        sa.Column('ventas_real', sa.Numeric(10, 2), nullable=False),
        sa.Column('demanda_base', sa.Numeric(10, 2), nullable=False),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('sku', 'anio', 'mes', name='uq_quiebres_sku_anio_mes'),
    )
    op.create_index('ix_quiebres_sku', 'quiebres_stock_2025', ['sku'])


def downgrade() -> None:
    op.drop_index('ix_quiebres_sku', 'quiebres_stock_2025')
    op.drop_table('quiebres_stock_2025')
