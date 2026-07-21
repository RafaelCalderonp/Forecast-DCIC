-- ============================================================
-- MIGRACIÓN 003 — Tablas Holt-Winters y Métricas
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_hw_2027 (
    sku        VARCHAR(50) NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
    mes        SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    cantidad   INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (sku, mes)
);

CREATE TABLE IF NOT EXISTS forecast_metricas (
    sku          VARCHAR(50) NOT NULL,
    modelo       VARCHAR(50) NOT NULL,
    mape         NUMERIC(8,2),
    bias_pct     NUMERIC(8,2),
    n_meses      INTEGER,
    updated_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (sku, modelo)
);

-- Verificación
SELECT 'forecast_hw_2027'  AS tabla, COUNT(*) AS filas FROM forecast_hw_2027
UNION ALL
SELECT 'forecast_metricas', COUNT(*) FROM forecast_metricas;
