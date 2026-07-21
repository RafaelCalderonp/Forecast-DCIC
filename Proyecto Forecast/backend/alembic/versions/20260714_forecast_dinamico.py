"""forecast dinamico: 6 tablas nuevas + vista materializada

Revision ID: 20260714_forecast
Revises:
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260714_forecast'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. segmentacion_abc_xyz
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS segmentacion_abc_xyz (
        id                    SERIAL PRIMARY KEY,
        sku                   VARCHAR(50) NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
        canal                 VARCHAR(50) NOT NULL,
        periodo_inicio        DATE        NOT NULL,
        periodo_fin           DATE        NOT NULL,
        clase_abc             CHAR(1)     NOT NULL CHECK (clase_abc IN ('A','B','C')),
        clase_xyz             CHAR(1)     NOT NULL CHECK (clase_xyz IN ('X','Y','Z')),
        coeficiente_variacion NUMERIC(8,4),
        revenue_total         NUMERIC(14,2),
        unidades_total        INTEGER,
        pct_revenue_acum      NUMERIC(6,4),
        calculado_en          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_abcxyz_sku_canal_periodo UNIQUE (sku, canal, periodo_inicio)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_abcxyz_clase ON segmentacion_abc_xyz(clase_abc, clase_xyz)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_abcxyz_sku   ON segmentacion_abc_xyz(sku)")

    # ------------------------------------------------------------------
    # 2. lift_factors
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS lift_factors (
        id              SERIAL PRIMARY KEY,
        nombre_evento   VARCHAR(100) NOT NULL,
        canal           VARCHAR(50),
        sku_pattern     VARCHAR(100),
        fecha_inicio    DATE        NOT NULL,
        fecha_fin       DATE        NOT NULL,
        multiplicador   NUMERIC(6,3) NOT NULL DEFAULT 1.0 CHECK (multiplicador > 0),
        tipo            VARCHAR(20)  NOT NULL DEFAULT 'manual'
                        CHECK (tipo IN ('manual','historico','sugerido')),
        notas           TEXT,
        creado_por      INTEGER      REFERENCES usuarios(id),
        creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        actualizado_en  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_lift_fechas CHECK (fecha_fin >= fecha_inicio)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lift_fechas ON lift_factors(fecha_inicio, fecha_fin)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lift_canal  ON lift_factors(canal)")

    # ------------------------------------------------------------------
    # 3. forecast_resultados (particionada por mes)
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS forecast_resultados (
        id                BIGSERIAL,
        sku               VARCHAR(50)  NOT NULL,
        canal             VARCHAR(50)  NOT NULL,
        periodo           DATE         NOT NULL,
        forecast_base     NUMERIC(12,2) NOT NULL,
        lift_aplicado     NUMERIC(6,3)  NOT NULL DEFAULT 1.0,
        forecast_ajustado NUMERIC(12,2) NOT NULL,
        stock_disponible  INTEGER,
        forecast_final    NUMERIC(12,2) NOT NULL,
        ventas_reales     NUMERIC(12,2),
        mape              NUMERIC(8,4),
        bias              NUMERIC(10,2),
        dci               NUMERIC(8,2),
        modelo_version    VARCHAR(20)  NOT NULL DEFAULT 'hw_v1',
        parametros_hw     JSONB,
        es_override       BOOLEAN      NOT NULL DEFAULT FALSE,
        calculado_en      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        PRIMARY KEY (id, periodo)
    ) PARTITION BY RANGE (periodo)
    """)

    for year_month in [
        ('2026-07-01', '2026-08-01'),
        ('2026-08-01', '2026-09-01'),
        ('2026-09-01', '2026-10-01'),
        ('2026-10-01', '2026-11-01'),
        ('2026-11-01', '2026-12-01'),
        ('2026-12-01', '2027-01-01'),
        ('2027-01-01', '2027-02-01'),
        ('2027-02-01', '2027-03-01'),
        ('2027-03-01', '2027-04-01'),
        ('2027-04-01', '2027-05-01'),
        ('2027-05-01', '2027-06-01'),
        ('2027-06-01', '2027-07-01'),
        ('2027-07-01', '2027-08-01'),
        ('2027-08-01', '2027-09-01'),
        ('2027-09-01', '2027-10-01'),
        ('2027-10-01', '2027-11-01'),
        ('2027-11-01', '2027-12-01'),
        ('2027-12-01', '2028-01-01'),
    ]:
        name = f"forecast_resultados_{year_month[0][:7].replace('-', '_')}"
        op.execute(f"""
        CREATE TABLE IF NOT EXISTS {name}
            PARTITION OF forecast_resultados
            FOR VALUES FROM ('{year_month[0]}') TO ('{year_month[1]}')
        """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_fr_sku_canal ON forecast_resultados(sku, canal, periodo)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fr_periodo   ON forecast_resultados(periodo)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fr_mape      ON forecast_resultados(mape) WHERE mape IS NOT NULL")

    # ------------------------------------------------------------------
    # 4. overrides_forecast
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS overrides_forecast (
        id              SERIAL PRIMARY KEY,
        sku             VARCHAR(50)   NOT NULL REFERENCES productos(sku),
        canal           VARCHAR(50)   NOT NULL,
        periodo         DATE          NOT NULL,
        valor_original  NUMERIC(12,2) NOT NULL,
        valor_override  NUMERIC(12,2) NOT NULL,
        motivo          TEXT          NOT NULL,
        aplicado        BOOLEAN       NOT NULL DEFAULT FALSE,
        creado_por      INTEGER       REFERENCES usuarios(id),
        creado_en       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_override_sku_canal_periodo UNIQUE (sku, canal, periodo)
    )
    """)

    # ------------------------------------------------------------------
    # 5. alertas_forecast
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS alertas_forecast (
        id          BIGSERIAL PRIMARY KEY,
        tipo_alerta VARCHAR(50) NOT NULL CHECK (tipo_alerta IN (
                        'MAPE_ALTO','BIAS_ACUMULADO','OOS_RIESGO',
                        'FILL_RATE_BAJO','DCI_CRITICO','DESVIO_QUINCENAL')),
        sku         VARCHAR(50)   NOT NULL,
        canal       VARCHAR(50),
        periodo     DATE          NOT NULL,
        valor_actual  NUMERIC(12,4) NOT NULL,
        umbral        NUMERIC(12,4) NOT NULL,
        severidad   VARCHAR(10)   NOT NULL DEFAULT 'MEDIA'
                    CHECK (severidad IN ('BAJA','MEDIA','ALTA','CRITICA')),
        mensaje     TEXT          NOT NULL,
        resuelta    BOOLEAN       NOT NULL DEFAULT FALSE,
        resuelta_en TIMESTAMPTZ,
        creado_en   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_alertas_activas ON alertas_forecast(resuelta, creado_en) WHERE resuelta = FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alertas_tipo    ON alertas_forecast(tipo_alerta, periodo)")

    # ------------------------------------------------------------------
    # 6. ordenes_compra_sugeridas
    # ------------------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_compra_sugeridas (
        id                  SERIAL PRIMARY KEY,
        sku                 VARCHAR(50)   NOT NULL REFERENCES productos(sku),
        fecha_sugerida      DATE          NOT NULL,
        fecha_necesidad     DATE          NOT NULL,
        cantidad_sugerida   INTEGER       NOT NULL CHECK (cantidad_sugerida > 0),
        stock_actual        INTEGER       NOT NULL DEFAULT 0,
        forecast_demanda    NUMERIC(12,2) NOT NULL,
        lead_time_dias      INTEGER       NOT NULL DEFAULT 30,
        stock_seguridad     INTEGER       NOT NULL DEFAULT 0,
        proveedor_sugerido  VARCHAR(100),
        costo_estimado      NUMERIC(14,2),
        estado              VARCHAR(20)   NOT NULL DEFAULT 'pendiente'
                            CHECK (estado IN ('pendiente','aprobada','rechazada','emitida')),
        clase_abc           CHAR(1),
        notas               TEXT,
        generado_en         TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        actualizado_en      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_oc_estado ON ordenes_compra_sugeridas(estado, fecha_sugerida)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_oc_sku    ON ordenes_compra_sugeridas(sku)")

    # ------------------------------------------------------------------
    # 7. Vista materializada mv_forecast_resumen
    # ------------------------------------------------------------------
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_resumen AS
    SELECT
        fr.sku,
        fr.canal,
        fr.periodo,
        p.descripcion   AS descripcion_producto,
        m.nombre        AS marca,
        c.nombre        AS categoria,
        saz.clase_abc,
        saz.clase_xyz,
        fr.forecast_base,
        fr.forecast_ajustado,
        fr.forecast_final,
        fr.ventas_reales,
        fr.mape,
        fr.bias,
        fr.dci,
        fr.lift_aplicado,
        fr.es_override,
        CASE
            WHEN fr.mape > 0.50 THEN 'CRITICO'
            WHEN fr.mape > 0.30 THEN 'ALTO'
            WHEN fr.mape > 0.15 THEN 'MEDIO'
            ELSE 'OK'
        END AS estado_mape,
        (SELECT COUNT(*) FROM alertas_forecast a
         WHERE a.sku = fr.sku AND a.canal = fr.canal
           AND a.periodo = fr.periodo AND a.resuelta = FALSE) AS alertas_activas
    FROM forecast_resultados fr
    JOIN productos p ON p.sku = fr.sku
    JOIN marcas m    ON m.id  = p.marca_id
    JOIN categorias c ON c.id = p.categoria_id
    LEFT JOIN segmentacion_abc_xyz saz
        ON saz.sku = fr.sku AND saz.canal = fr.canal
       AND fr.periodo BETWEEN saz.periodo_inicio AND saz.periodo_fin
    WITH NO DATA
    """)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_fr_sku_canal_periodo
        ON mv_forecast_resumen(sku, canal, periodo)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_fr_clase ON mv_forecast_resumen(clase_abc, clase_xyz)")

    # ------------------------------------------------------------------
    # 8. Lift factor inicial: CyberDay Nov 2026
    # ------------------------------------------------------------------
    op.execute("""
    INSERT INTO lift_factors (nombre_evento, canal, sku_pattern, fecha_inicio, fecha_fin, multiplicador, tipo, notas)
    VALUES ('CyberDay_Nov2026', NULL, NULL, '2026-11-01', '2026-11-30', 1.80, 'manual',
            'Multiplicador base CyberDay noviembre 2026. Ajustar por categoría según histórico.')
    ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_forecast_resumen CASCADE")
    op.execute("DROP TABLE IF EXISTS ordenes_compra_sugeridas CASCADE")
    op.execute("DROP TABLE IF EXISTS alertas_forecast CASCADE")
    op.execute("DROP TABLE IF EXISTS overrides_forecast CASCADE")
    op.execute("DROP TABLE IF EXISTS forecast_resultados CASCADE")
    op.execute("DROP TABLE IF EXISTS lift_factors CASCADE")
    op.execute("DROP TABLE IF EXISTS segmentacion_abc_xyz CASCADE")
