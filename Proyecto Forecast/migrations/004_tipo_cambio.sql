-- ============================================================
-- MIGRACIÓN 004 — Tipo de Cambio CLP/USD
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS tipo_cambio (
    fecha       DATE        NOT NULL PRIMARY KEY,
    usd_clp     NUMERIC(10, 2) NOT NULL,   -- cuántos CLP vale 1 USD
    fuente      VARCHAR(50) DEFAULT 'manual',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para consultas por rango de fechas
CREATE INDEX IF NOT EXISTS idx_tipo_cambio_fecha ON tipo_cambio (fecha DESC);

-- Verificación
SELECT 'tipo_cambio' AS tabla, COUNT(*) AS filas FROM tipo_cambio;
