-- ============================================================
-- FORECAST DCIC - Schema PostgreSQL
-- ============================================================

-- ─────────────────────────────────────────
-- TABLA: temporadas
-- ─────────────────────────────────────────
CREATE TABLE temporadas (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE,  -- ej: 'Verano 2026', 'Invierno 2026'
    fecha_inicio    DATE,
    fecha_fin       DATE,
    activa          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- TABLA: marcas
-- ─────────────────────────────────────────
CREATE TABLE marcas (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(100) NOT NULL UNIQUE
);

-- ─────────────────────────────────────────
-- TABLA: categorias
-- ─────────────────────────────────────────
CREATE TABLE categorias (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(100) NOT NULL UNIQUE
);

-- ─────────────────────────────────────────
-- TABLA: productos
-- ─────────────────────────────────────────
CREATE TABLE productos (
    sku                 VARCHAR(50) PRIMARY KEY,
    marca_id            INTEGER NOT NULL REFERENCES marcas(id),
    categoria_id        INTEGER NOT NULL REFERENCES categorias(id),
    temporada_id        INTEGER REFERENCES temporadas(id),
    descripcion         TEXT,
    precio_venta_bruto  NUMERIC(12,2) NOT NULL DEFAULT 0,
    precio_venta_neto   NUMERIC(12,2) NOT NULL DEFAULT 0,
    activo              BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- TABLA: packs
-- ─────────────────────────────────────────
CREATE TABLE packs (
    sku                 VARCHAR(50) PRIMARY KEY,
    marca_id            INTEGER NOT NULL REFERENCES marcas(id),
    categoria_id        INTEGER NOT NULL REFERENCES categorias(id),
    temporada_id        INTEGER REFERENCES temporadas(id),
    descripcion         TEXT,
    precio_venta_bruto  NUMERIC(12,2) NOT NULL DEFAULT 0,
    precio_venta_neto   NUMERIC(12,2) NOT NULL DEFAULT 0,
    activo              BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- TABLA: pack_componentes
-- Relación Pack → SKUs de productos que lo componen
-- ─────────────────────────────────────────
CREATE TABLE pack_componentes (
    id              SERIAL PRIMARY KEY,
    pack_sku        VARCHAR(50) NOT NULL REFERENCES packs(sku) ON DELETE CASCADE,
    producto_sku    VARCHAR(50) NOT NULL REFERENCES productos(sku),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    UNIQUE (pack_sku, producto_sku)
);

-- ─────────────────────────────────────────
-- TABLA: forecast
-- Un registro por SKU + Año + Mes
-- ─────────────────────────────────────────
CREATE TABLE forecast (
    id              SERIAL PRIMARY KEY,
    sku             VARCHAR(50) NOT NULL REFERENCES productos(sku),
    temporada_id    INTEGER REFERENCES temporadas(id),
    anio            SMALLINT NOT NULL,
    mes             SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    cantidad        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (sku, anio, mes)
);

-- ─────────────────────────────────────────
-- TABLA: ventas
-- ─────────────────────────────────────────
CREATE TABLE ventas (
    id                   SERIAL PRIMARY KEY,
    sku                  VARCHAR(50) NOT NULL REFERENCES productos(sku),
    fecha                DATE NOT NULL,
    canal                VARCHAR(50),            -- ej: 'ML', 'Falabella', 'Directo'
    cantidad             INTEGER NOT NULL CHECK (cantidad >= 0),
    unidades_devueltas   INTEGER NOT NULL DEFAULT 0 CHECK (unidades_devueltas >= 0),
    precio_lista_bruto   NUMERIC(12,2),          -- Precio sin descuento (bruto)
    valor_unitario_neto  NUMERIC(12,2),          -- Precio de venta real (neto)
    costo_unitario_clp   NUMERIC(12,2),          -- Costo de la unidad
    margen_clp           NUMERIC(12,2),          -- Margen absoluto en CLP
    margen_pct           NUMERIC(6,4),           -- Margen porcentual ej: 0.3250 = 32.50%
    descripcion_producto TEXT,                   -- Descripción desde ERP (para validación)
    categoria_erp        VARCHAR(100),           -- Categoría según ERP
    marca_erp            VARCHAR(100),           -- Marca según ERP
    created_at           TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- TABLA: stock
-- Un registro por SKU (actualizable con fecha de corte)
-- ─────────────────────────────────────────
CREATE TABLE stock (
    sku                 VARCHAR(50) PRIMARY KEY REFERENCES productos(sku),
    stock_base          INTEGER NOT NULL DEFAULT 0,   -- Bodega propia / base
    stock_full_ml       INTEGER NOT NULL DEFAULT 0,   -- Bodega Full Mercado Libre
    stock_full_fala     INTEGER NOT NULL DEFAULT 0,   -- Bodega Full Falabella
    bodega_transito     INTEGER NOT NULL DEFAULT 0,   -- En tránsito (fecha ETA)
    por_arribar         INTEGER NOT NULL DEFAULT 0,   -- Confirmado, pendiente llegada
    pi                  INTEGER NOT NULL DEFAULT 0,   -- Purchase Intent / pre-compra
    eta_transito        DATE,   -- ETA para bodega_transito
    eta_arribar         DATE,   -- ETA para por_arribar
    eta_pi              DATE,   -- ETA para PI
    fecha_actualizacion DATE NOT NULL DEFAULT CURRENT_DATE,
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- ÍNDICES para performance
-- ─────────────────────────────────────────
CREATE INDEX idx_forecast_sku        ON forecast(sku);
CREATE INDEX idx_forecast_anio_mes   ON forecast(anio, mes);
CREATE INDEX idx_ventas_sku          ON ventas(sku);
CREATE INDEX idx_ventas_fecha        ON ventas(fecha);
CREATE INDEX idx_pack_componentes_pack ON pack_componentes(pack_sku);
CREATE INDEX idx_productos_marca     ON productos(marca_id);
CREATE INDEX idx_productos_categoria ON productos(categoria_id);
CREATE INDEX idx_productos_temporada ON productos(temporada_id);

-- ─────────────────────────────────────────
-- TRIGGER: updated_at automático
-- ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_productos_updated_at
    BEFORE UPDATE ON productos
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_packs_updated_at
    BEFORE UPDATE ON packs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_forecast_updated_at
    BEFORE UPDATE ON forecast
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_stock_updated_at
    BEFORE UPDATE ON stock
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─────────────────────────────────────────
-- DATOS INICIALES (seed básico)
-- ─────────────────────────────────────────
INSERT INTO temporadas (nombre, fecha_inicio, fecha_fin) VALUES
    ('Verano',           NULL, NULL),
    ('Invierno',         NULL, NULL),
    ('No Estacional',    NULL, NULL),
    ('Verano/Rotativo',  NULL, NULL);
