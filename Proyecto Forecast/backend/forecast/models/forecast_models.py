from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Date, Text,
    ForeignKey, CheckConstraint, UniqueConstraint, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import DateTime
from sqlalchemy.sql import func
from database import Base
import models.models  # registra Producto, Usuario etc. en el mismo Base


class SegmentacionAbcXyz(Base):
    __tablename__ = "segmentacion_abc_xyz"
    __table_args__ = (
        UniqueConstraint("sku", "canal", "periodo_inicio", name="uq_abcxyz_sku_canal_periodo"),
    )
    id                    = Column(Integer, primary_key=True)
    sku                   = Column(String(50), ForeignKey("productos.sku", ondelete="CASCADE"), nullable=False)
    canal                 = Column(String(50), nullable=False)
    periodo_inicio        = Column(Date, nullable=False)
    periodo_fin           = Column(Date, nullable=False)
    clase_abc             = Column(String(1), nullable=False)
    clase_xyz             = Column(String(1), nullable=False)
    coeficiente_variacion = Column(Numeric(8, 4))
    revenue_total         = Column(Numeric(14, 2))
    unidades_total        = Column(Integer)
    pct_revenue_acum      = Column(Numeric(6, 4))
    calculado_en          = Column(DateTime(timezone=True), server_default=func.now())


class LiftFactor(Base):
    __tablename__ = "lift_factors"
    id             = Column(Integer, primary_key=True)
    nombre_evento  = Column(String(100), nullable=False)
    canal          = Column(String(50))          # NULL = todos los canales
    sku_pattern    = Column(String(100))         # NULL = todos los SKUs
    fecha_inicio   = Column(Date, nullable=False)
    fecha_fin      = Column(Date, nullable=False)
    multiplicador  = Column(Numeric(6, 3), nullable=False, default=1.0)
    tipo           = Column(String(20), nullable=False, default="manual")
    notas          = Column(Text)
    creado_por     = Column(Integer, ForeignKey("usuarios.id"))
    creado_en      = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ForecastResultado(Base):
    # Tabla particionada — SQLAlchemy puede usarla para INSERT/SELECT
    __tablename__ = "forecast_resultados"
    id                = Column(BigInteger, primary_key=True)
    sku               = Column(String(50), nullable=False)
    canal             = Column(String(50), nullable=False)
    periodo           = Column(Date, nullable=False)
    forecast_base     = Column(Numeric(12, 2), nullable=False)
    lift_aplicado     = Column(Numeric(6, 3), nullable=False, default=1.0)
    forecast_ajustado = Column(Numeric(12, 2), nullable=False)
    stock_disponible  = Column(Integer)
    forecast_final    = Column(Numeric(12, 2), nullable=False)
    ventas_reales     = Column(Numeric(12, 2))
    mape              = Column(Numeric(8, 4))
    bias              = Column(Numeric(10, 2))
    dci               = Column(Numeric(8, 2))
    modelo_version    = Column(String(20), nullable=False, default="hw_v1")
    parametros_hw     = Column(JSONB)
    es_override       = Column(Boolean, nullable=False, default=False)
    calculado_en      = Column(DateTime(timezone=True), server_default=func.now())


class OverrideForecast(Base):
    __tablename__ = "overrides_forecast"
    __table_args__ = (
        UniqueConstraint("sku", "canal", "periodo", name="uq_override_sku_canal_periodo"),
    )
    id             = Column(Integer, primary_key=True)
    sku            = Column(String(50), ForeignKey("productos.sku"), nullable=False)
    canal          = Column(String(50), nullable=False)
    periodo        = Column(Date, nullable=False)
    valor_original = Column(Numeric(12, 2), nullable=False)
    valor_override = Column(Numeric(12, 2), nullable=False)
    motivo         = Column(Text, nullable=False)
    aplicado       = Column(Boolean, nullable=False, default=False)
    creado_por     = Column(Integer, ForeignKey("usuarios.id"))
    creado_en      = Column(DateTime(timezone=True), server_default=func.now())


class AlertaForecast(Base):
    __tablename__ = "alertas_forecast"
    id           = Column(BigInteger, primary_key=True)
    tipo_alerta  = Column(String(50), nullable=False)
    sku          = Column(String(50), nullable=False)
    canal        = Column(String(50))
    periodo      = Column(Date, nullable=False)
    valor_actual = Column(Numeric(12, 4), nullable=False)
    umbral       = Column(Numeric(12, 4), nullable=False)
    severidad    = Column(String(10), nullable=False, default="MEDIA")
    mensaje      = Column(Text, nullable=False)
    resuelta     = Column(Boolean, nullable=False, default=False)
    resuelta_en  = Column(DateTime(timezone=True))
    creado_en    = Column(DateTime(timezone=True), server_default=func.now())


class OrdenCompraSugerida(Base):
    __tablename__ = "ordenes_compra_sugeridas"
    id                = Column(Integer, primary_key=True)
    sku               = Column(String(50), ForeignKey("productos.sku"), nullable=False)
    fecha_sugerida    = Column(Date, nullable=False)
    fecha_necesidad   = Column(Date, nullable=False)
    cantidad_sugerida = Column(Integer, nullable=False)
    stock_actual      = Column(Integer, nullable=False, default=0)
    forecast_demanda  = Column(Numeric(12, 2), nullable=False)
    lead_time_dias    = Column(Integer, nullable=False, default=30)
    stock_seguridad   = Column(Integer, nullable=False, default=0)
    proveedor_sugerido = Column(String(100))
    costo_estimado    = Column(Numeric(14, 2))
    estado            = Column(String(20), nullable=False, default="pendiente")
    clase_abc         = Column(String(1))
    notas             = Column(Text)
    generado_en       = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_en    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
