-- ============================================================
-- MIGRACIÓN 006 — Historial de sincronizaciones ERP
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS sync_log (
    id               SERIAL PRIMARY KEY,
    job_id           UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    fuente           VARCHAR(20),
    desde            DATE,
    hasta            DATE,
    estado           VARCHAR(20) DEFAULT 'running',  -- running | done | error
    insertados       INTEGER DEFAULT 0,
    actualizados     INTEGER DEFAULT 0,
    omitidos         INTEGER DEFAULT 0,
    errores_fk       INTEGER DEFAULT 0,
    errores_otros    INTEGER DEFAULT 0,
    sin_sku          INTEGER DEFAULT 0,
    meses_procesados INTEGER DEFAULT 0,
    filas_api        INTEGER DEFAULT 0,
    canales_api      JSONB,        -- { canal: total_bruta } recibido de la API
    skus_faltantes   JSONB,        -- lista de SKUs con FK violation
    started_at       TIMESTAMP DEFAULT NOW(),
    finished_at      TIMESTAMP,
    error_msg        TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_log_started ON sync_log (started_at DESC);

SELECT 'sync_log' AS tabla, COUNT(*) AS filas FROM sync_log;
