-- ============================================================
-- MIGRACIÓN FASE 1 — DCIC Forecast
-- Ejecutar en orden, todo en una transacción
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. ROLES Y USUARIOS
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(50) NOT NULL UNIQUE,  -- 'admin', 'editor', 'viewer'
    descripcion TEXT
);

INSERT INTO roles (nombre, descripcion) VALUES
    ('admin',  'Acceso total: costos, márgenes, desbloqueo de filas, gestión de usuarios'),
    ('editor', 'Puede editar forecast y ajustes, no ve costos'),
    ('viewer', 'Solo lectura')
    ON CONFLICT (nombre) DO NOTHING;

CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    email          VARCHAR(200) NOT NULL UNIQUE,
    nombre         VARCHAR(150) NOT NULL,
    password_hash  VARCHAR(200) NOT NULL,
    rol_id         INTEGER NOT NULL REFERENCES roles(id) DEFAULT 3,  -- viewer por defecto
    activo         BOOLEAN DEFAULT TRUE,
    ultimo_acceso  TIMESTAMP,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

-- Usuario admin inicial (password: Admin1234! — cambiar inmediatamente)
-- Hash bcrypt generado fuera de SQL, se actualiza desde el script Python
INSERT INTO usuarios (email, nombre, password_hash, rol_id) VALUES
    ('admin@dcic.cl', 'Administrador DCIC', 'CHANGE_ME_RUN_PYTHON_SCRIPT', 1)
    ON CONFLICT (email) DO NOTHING;

CREATE OR REPLACE TRIGGER trg_usuarios_updated_at
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─────────────────────────────────────────────────────────────
-- 2. SUBCATEGORÍAS
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS subcategorias (
    id           SERIAL PRIMARY KEY,
    nombre       VARCHAR(150) NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
    activo       BOOLEAN DEFAULT TRUE,
    UNIQUE (nombre, categoria_id)
);

CREATE INDEX IF NOT EXISTS idx_subcategorias_categoria ON subcategorias(categoria_id);

-- ─────────────────────────────────────────────────────────────
-- 3. CANALES DE VENTA
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS canales (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    codigo VARCHAR(30)  NOT NULL UNIQUE,
    activo BOOLEAN DEFAULT TRUE
);

INSERT INTO canales (nombre, codigo) VALUES
    ('Falabella',      'FALA'),
    ('Mercado Libre',  'ML'),
    ('Walmart',        'WALMART'),
    ('Paris',          'PARIS'),
    ('Ripley',         'RIPLEY'),
    ('Venta Directa',  'DIRECTO')
    ON CONFLICT (nombre) DO NOTHING;
-- Las 9 páginas propias se agregan cuando el usuario entregue los nombres exactos

-- ─────────────────────────────────────────────────────────────
-- 4. EVENTOS COMERCIALES (para excluir de cálculo de quiebres)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS eventos_comerciales (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(100) NOT NULL,
    mes                 SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    dia_inicio          SMALLINT NOT NULL CHECK (dia_inicio BETWEEN 1 AND 31),
    dia_fin             SMALLINT NOT NULL CHECK (dia_fin BETWEEN 1 AND 31),
    multiplicador_base  NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    aplica_todas_categorias BOOLEAN DEFAULT TRUE,
    activo              BOOLEAN DEFAULT TRUE,
    notas               TEXT
);

INSERT INTO eventos_comerciales (nombre, mes, dia_inicio, dia_fin, multiplicador_base, notas) VALUES
    ('Día de la Madre',  5,  8, 10, 1.60, 'Segunda semana de mayo'),
    ('CyberDay',         5, 19, 21, 2.20, 'Tercera semana de mayo — excluir del cálculo de tasa normal'),
    ('Hot Sale',         6, 15, 17, 1.50, 'Fecha variable, revisar anualmente'),
    ('Fiestas Patrias',  9, 14, 20, 1.40, 'Semana 18 de septiembre'),
    ('CyberMonday',     11, 25, 27, 2.50, 'Última semana de noviembre'),
    ('Black Friday',    11, 28, 28, 2.00, 'Viernes post-CyberMonday'),
    ('Pre-Navidad',     12,  1, 19, 1.80, 'Primera quincena de diciembre'),
    ('Navidad',         12, 20, 24, 2.80, 'Pico final de Navidad')
    ON CONFLICT DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 5. NUEVOS CAMPOS EN PRODUCTOS
-- ─────────────────────────────────────────────────────────────

ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS subcategoria_id          INTEGER REFERENCES subcategorias(id),
    ADD COLUMN IF NOT EXISTS tipo                     VARCHAR(50),
    ADD COLUMN IF NOT EXISTS precio_minimo_evento     NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS precio_liquidacion       NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS con_piedras_reliquidacion BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS costo_unitario_neto      NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS grupo_pareto             CHAR(1),
    ADD COLUMN IF NOT EXISTS prioridad_compra         SMALLINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS moq                      INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS recomendacion            TEXT,
    ADD COLUMN IF NOT EXISTS comentario_compra        TEXT,
    ADD COLUMN IF NOT EXISTS es_piedra                BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rehacer_forecast         BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS cerrado                  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS al_31_mayo               INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_productos_subcategoria ON productos(subcategoria_id);
CREATE INDEX IF NOT EXISTS idx_productos_pareto       ON productos(grupo_pareto);

-- ─────────────────────────────────────────────────────────────
-- 6. NUEVOS CAMPOS EN FORECAST
-- ─────────────────────────────────────────────────────────────

ALTER TABLE forecast
    ADD COLUMN IF NOT EXISTS ajuste               INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS venta_anio_anterior  INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS venta_dos_anios      INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consumo_pack         INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pxq                  NUMERIC(14,2);

-- ─────────────────────────────────────────────────────────────
-- 7. TABLA FORECAST POR CANAL (2027+)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS forecast_canal (
    id              BIGSERIAL PRIMARY KEY,
    sku             VARCHAR(50)  NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
    canal_id        INTEGER      NOT NULL REFERENCES canales(id),
    anio            SMALLINT     NOT NULL CHECK (anio >= 2026),
    mes             SMALLINT     NOT NULL CHECK (mes BETWEEN 1 AND 12),
    cantidad        INTEGER      NOT NULL DEFAULT 0,
    ajuste          INTEGER      DEFAULT 0,
    precio_canal    NUMERIC(12,2),
    pxq             NUMERIC(14,2),
    margen_pct      NUMERIC(6,4),
    fuente          VARCHAR(50)  DEFAULT 'manual',  -- 'manual', 'api', 'proyeccion'
    created_at      TIMESTAMP    DEFAULT NOW(),
    updated_at      TIMESTAMP    DEFAULT NOW(),
    UNIQUE (sku, canal_id, anio, mes)
);

CREATE INDEX IF NOT EXISTS idx_fc_sku      ON forecast_canal(sku);
CREATE INDEX IF NOT EXISTS idx_fc_canal    ON forecast_canal(canal_id);
CREATE INDEX IF NOT EXISTS idx_fc_anio_mes ON forecast_canal(anio, mes);

CREATE OR REPLACE TRIGGER trg_forecast_canal_updated_at
    BEFORE UPDATE ON forecast_canal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─────────────────────────────────────────────────────────────
-- 8. TABLA PLAN DE COMPRAS (resultado del reporte)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS plan_compras (
    id                      BIGSERIAL PRIMARY KEY,
    sku                     VARCHAR(50) NOT NULL REFERENCES productos(sku),
    fecha_calculo           DATE NOT NULL DEFAULT CURRENT_DATE,
    mes_inicio              SMALLINT NOT NULL,   -- mes desde donde se calcula
    anio_inicio             SMALLINT NOT NULL,
    stock_actual            INTEGER DEFAULT 0,
    llegadas_confirmadas    INTEGER DEFAULT 0,
    demanda_lead_time       INTEGER DEFAULT 0,
    stock_al_llegar         INTEGER DEFAULT 0,
    demanda_cobertura       INTEGER DEFAULT 0,
    stock_seguridad         INTEGER DEFAULT 0,
    cantidad_comprar        INTEGER DEFAULT 0,
    moq_aplicado            INTEGER DEFAULT 0,
    costo_total_estimado    NUMERIC(14,2),
    dias_cobertura          SMALLINT DEFAULT 0,
    estado_semaforo         VARCHAR(20),  -- 'critico','rojo','amarillo','verde','gris','sobrestock'
    temporada_activa        BOOLEAN DEFAULT TRUE,
    compra_diferida         BOOLEAN DEFAULT FALSE,
    motivo_diferimiento     TEXT,
    faltante_sep            INTEGER DEFAULT 0,
    faltante_oct            INTEGER DEFAULT 0,
    faltante_nov            INTEGER DEFAULT 0,
    faltante_dic            INTEGER DEFAULT 0,
    notas                   TEXT,
    created_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_compras_sku        ON plan_compras(sku);
CREATE INDEX IF NOT EXISTS idx_plan_compras_fecha      ON plan_compras(fecha_calculo);
CREATE INDEX IF NOT EXISTS idx_plan_compras_semaforo   ON plan_compras(estado_semaforo);

COMMIT;

-- ─────────────────────────────────────────────────────────────
-- VERIFICACIÓN POST-MIGRACIÓN
-- ─────────────────────────────────────────────────────────────
-- Ejecutar después del COMMIT para verificar:
/*
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'productos' ORDER BY ordinal_position;

SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'forecast' ORDER BY ordinal_position;
*/
