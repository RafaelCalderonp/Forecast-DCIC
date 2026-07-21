-- ============================================================
-- MIGRACIÓN 001 — Preparación para producción
-- Ejecutar UNA VEZ con el servidor detenido
-- psql -U postgres -d forecast_dcic -f 001_produccion.sql
-- ============================================================

-- 1. Ventas: columnas para idempotencia ERP
ALTER TABLE ventas
    ADD COLUMN IF NOT EXISTS id_externo VARCHAR(150),
    ADD COLUMN IF NOT EXISTS activo     BOOLEAN NOT NULL DEFAULT TRUE;

-- Índice único para garantizar que el mismo registro del ERP no se duplique
CREATE UNIQUE INDEX IF NOT EXISTS uq_ventas_id_externo
    ON ventas (id_externo)
    WHERE id_externo IS NOT NULL;

-- Índice de rendimiento para consultas por período y canal
CREATE INDEX IF NOT EXISTS idx_ventas_sku_fecha
    ON ventas (sku, fecha);

-- 2. Productos: columnas que faltaban en el ORM
ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS grupo_pareto        VARCHAR(1),
    ADD COLUMN IF NOT EXISTS costo_unitario_neto NUMERIC(12,2) DEFAULT 0;

-- 3. Marcar ventas históricas de Excel como fuente conocida
UPDATE ventas
    SET fuente = 'excel_historico'
    WHERE fuente IS NULL;

-- Verificación final
SELECT
    'ventas'    AS tabla,
    COUNT(*)    AS filas,
    COUNT(id_externo) AS con_id_externo,
    COUNT(*) FILTER (WHERE activo = FALSE) AS inactivas
FROM ventas
UNION ALL
SELECT
    'productos',
    COUNT(*),
    COUNT(grupo_pareto),
    COUNT(*) FILTER (WHERE activo = FALSE)
FROM productos;
