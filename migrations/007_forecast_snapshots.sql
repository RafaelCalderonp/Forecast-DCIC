-- ============================================================
-- MIGRACIÓN 007 — Snapshots históricos de forecast 2027
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS forecast_snapshots (
    id           SERIAL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL,
    descripcion  TEXT,
    crecimiento  NUMERIC(5,2),         -- phi_panel usado (%)
    usd_clp      NUMERIC(8,2),         -- tipo de cambio al momento
    total_skus   INTEGER,
    total_uds    BIGINT,
    creado_por   VARCHAR(100),
    creado_en    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forecast_snapshot_filas (
    snapshot_id  INTEGER NOT NULL REFERENCES forecast_snapshots(id) ON DELETE CASCADE,
    sku          VARCHAR(50) NOT NULL,
    canal        VARCHAR(100) NOT NULL,
    mes          SMALLINT NOT NULL,
    cantidad     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (snapshot_id, sku, canal, mes)
);

CREATE INDEX IF NOT EXISTS idx_snap_filas_snapshot ON forecast_snapshot_filas(snapshot_id);

SELECT 'forecast_snapshots creada OK' AS resultado;
