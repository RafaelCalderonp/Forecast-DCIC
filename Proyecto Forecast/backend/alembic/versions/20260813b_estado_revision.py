"""ordenes_compra_sugeridas: agrega estado 'revision_requerida' (circuit-breaker precio)

Revision ID: 20260813b_estado_revision
Revises: 20260813_ajuste_precio
Create Date: 2026-08-13

Panel expertos ago-2026 (Larraín): las OC de SKUs con alza de precio relevante
no deben aprobarse automáticamente — quedan en 'revision_requerida' hasta que
alguien del equipo comercial/compras las revise manualmente.
"""
from alembic import op

revision = '20260813b_estado_revision'
down_revision = '20260813_ajuste_precio'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ordenes_compra_sugeridas_estado_check', 'ordenes_compra_sugeridas', type_='check')
    op.create_check_constraint(
        'ordenes_compra_sugeridas_estado_check',
        'ordenes_compra_sugeridas',
        "estado IN ('pendiente', 'aprobada', 'rechazada', 'emitida', 'revision_requerida')",
    )


def downgrade() -> None:
    op.drop_constraint('ordenes_compra_sugeridas_estado_check', 'ordenes_compra_sugeridas', type_='check')
    op.create_check_constraint(
        'ordenes_compra_sugeridas_estado_check',
        'ordenes_compra_sugeridas',
        "estado IN ('pendiente', 'aprobada', 'rechazada', 'emitida')",
    )
