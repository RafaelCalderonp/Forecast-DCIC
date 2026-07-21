-- ============================================================
-- MIGRACIÓN 002 — Autenticación M2M (API Keys para ERP)
-- Ejecutar UNA VEZ en pgAdmin
-- ============================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,           -- ej: "ERP BSale", "ERP Wivo"
    key_hash    VARCHAR(200) NOT NULL UNIQUE,     -- SHA-256 del token real
    activo      BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por  INTEGER REFERENCES usuarios(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_uso  TIMESTAMPTZ
);

-- Índice para lookup rápido al validar cada request
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (key_hash) WHERE activo = TRUE;

-- Verificación
SELECT 'api_keys' AS tabla, COUNT(*) AS filas FROM api_keys;
