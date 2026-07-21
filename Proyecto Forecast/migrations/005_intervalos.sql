-- ============================================================
-- MIGRACIÓN 005 — Intervalos de Confianza del Forecast
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_intervalos (
    sku          VARCHAR(50)    NOT NULL,
    anio         SMALLINT       NOT NULL,
    mes          SMALLINT       NOT NULL CHECK (mes BETWEEN 1 AND 12),
    modelo       VARCHAR(50)    NOT NULL,   -- 'ancla_si_macro' | 'holt_winters'
    cantidad     INTEGER        NOT NULL,   -- forecast central
    lower_80     INTEGER,                   -- límite inferior 80% confianza
    upper_80     INTEGER,                   -- límite superior 80% confianza
    lower_95     INTEGER,                   -- límite inferior 95% confianza
    upper_95     INTEGER,                   -- límite superior 95% confianza
    mape_usado   NUMERIC(8,2),              -- MAPE aplicado para calcular el intervalo
    updated_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (sku, anio, mes, modelo)
);

CREATE INDEX IF NOT EXISTS idx_fc_intervalos_sku ON forecast_intervalos (sku, anio);

SELECT 'forecast_intervalos' AS tabla, COUNT(*) AS filas FROM forecast_intervalos;
