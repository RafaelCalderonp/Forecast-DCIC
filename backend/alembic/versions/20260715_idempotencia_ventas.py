"""idempotencia ventas: UNIQUE(id_externo) para re-sync ERP sin duplicados

Revision ID: 20260715_idempotencia
Revises: 20260714_forecast
Create Date: 2026-07-15

Panel expertos (jun-2026): "sin constraint UNIQUE en ventas → re-sync del ERP
duplica registros". El id_externo es el identificador de línea en el ERP —
único por transacción, independiente de SKU o canal.

La constraint anterior (num_suborden, sku) cubría el 100% de los registros
actuales pero fallaría si num_suborden fuera NULL en futuras fuentes.
"""
from alembic import op

revision = '20260715_idempotencia'
down_revision = '20260714_forecast'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eliminar la constraint anterior (num_suborden, sku) — menos robusta
    op.drop_constraint('ventas_natural_key', 'ventas', type_='unique')

    # Nueva constraint por id_externo — clave única del ERP, siempre presente
    op.create_unique_constraint('ventas_uq_id_externo', 'ventas', ['id_externo'])


def downgrade() -> None:
    op.drop_constraint('ventas_uq_id_externo', 'ventas', type_='unique')
    op.create_unique_constraint('ventas_natural_key', 'ventas', ['num_suborden', 'sku'])
