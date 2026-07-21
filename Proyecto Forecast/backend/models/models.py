# models/models.py - Modelos SQLAlchemy

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Numeric, Boolean,
    Date, DateTime, Text, ForeignKey, CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from database import Base


class Temporada(Base):
    __tablename__ = "temporadas"
    id           = Column(Integer, primary_key=True)
    nombre       = Column(String(100), nullable=False, unique=True)
    fecha_inicio = Column(Date)
    fecha_fin    = Column(Date)
    activa       = Column(Boolean, default=True)
    created_at   = Column(DateTime, server_default=func.now())

    productos = relationship("Producto", back_populates="temporada")
    packs     = relationship("Pack", back_populates="temporada")
    forecasts = relationship("Forecast", back_populates="temporada")


class Marca(Base):
    __tablename__ = "marcas"
    id     = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)

    productos = relationship("Producto", back_populates="marca")
    packs     = relationship("Pack", back_populates="marca")


class Categoria(Base):
    __tablename__ = "categorias"
    id     = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)

    productos     = relationship("Producto", back_populates="categoria")
    packs         = relationship("Pack", back_populates="categoria")
    subcategorias = relationship("Subcategoria", back_populates="categoria")


class Subcategoria(Base):
    __tablename__ = "subcategorias"
    id           = Column(Integer, primary_key=True)
    nombre       = Column(String(150), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    activo       = Column(Boolean, default=True)

    categoria = relationship("Categoria", back_populates="subcategorias")
    productos = relationship("Producto", back_populates="subcategoria")


class Producto(Base):
    __tablename__ = "productos"
    sku                = Column(String(50), primary_key=True)
    marca_id           = Column(Integer, ForeignKey("marcas.id"), nullable=False)
    categoria_id       = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id    = Column(Integer, ForeignKey("subcategorias.id"))
    temporada_id       = Column(Integer, ForeignKey("temporadas.id"))
    descripcion        = Column(Text)
    precio_venta_bruto = Column(Numeric(12, 2), nullable=False, default=0)
    precio_venta_neto  = Column(Numeric(12, 2), nullable=False, default=0)
    activo             = Column(Boolean, default=True)
    por_discontinuar   = Column(Boolean, default=False)
    comentario         = Column(String(255))
    tipo_producto      = Column(String(150))
    grupo_pareto       = Column(String(1))   # A / B / C — usado en reporte de compras
    costo_unitario_neto = Column(Numeric(12, 2), default=0)
    created_at         = Column(DateTime, server_default=func.now())
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now())

    marca        = relationship("Marca", back_populates="productos")
    categoria    = relationship("Categoria", back_populates="productos")
    subcategoria = relationship("Subcategoria", back_populates="productos")
    temporada    = relationship("Temporada", back_populates="productos")
    stock        = relationship("Stock", back_populates="producto", uselist=False)
    ventas       = relationship("Venta", back_populates="producto")
    forecasts    = relationship("Forecast", back_populates="producto")
    en_packs     = relationship("PackComponente", back_populates="producto")


class Pack(Base):
    __tablename__ = "packs"
    sku                = Column(String(50), primary_key=True)
    marca_id           = Column(Integer, ForeignKey("marcas.id"), nullable=False)
    categoria_id       = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    temporada_id       = Column(Integer, ForeignKey("temporadas.id"))
    descripcion        = Column(Text)
    precio_venta_bruto = Column(Numeric(12, 2), nullable=False, default=0)
    precio_venta_neto  = Column(Numeric(12, 2), nullable=False, default=0)
    activo             = Column(Boolean, default=True)
    created_at         = Column(DateTime, server_default=func.now())
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now())

    marca       = relationship("Marca", back_populates="packs")
    categoria   = relationship("Categoria", back_populates="packs")
    temporada   = relationship("Temporada", back_populates="packs")
    componentes = relationship("PackComponente", back_populates="pack", cascade="all, delete-orphan")


class PackComponente(Base):
    __tablename__ = "pack_componentes"
    __table_args__ = (UniqueConstraint("pack_sku", "producto_sku"),)
    id           = Column(Integer, primary_key=True)
    pack_sku     = Column(String(50), ForeignKey("packs.sku", ondelete="CASCADE"), nullable=False)
    producto_sku = Column(String(50), ForeignKey("productos.sku"), nullable=False)
    cantidad     = Column(Integer, nullable=False)

    pack     = relationship("Pack", back_populates="componentes")
    producto = relationship("Producto", back_populates="en_packs")


class Forecast(Base):
    __tablename__ = "forecast"
    __table_args__ = (UniqueConstraint("sku", "anio", "mes"),)
    id           = Column(Integer, primary_key=True)
    sku          = Column(String(50), ForeignKey("productos.sku"), nullable=False)
    temporada_id = Column(Integer, ForeignKey("temporadas.id"))
    anio         = Column(SmallInteger, nullable=False)
    mes          = Column(SmallInteger, nullable=False)
    cantidad     = Column(Integer, nullable=False, default=0)
    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    producto  = relationship("Producto", back_populates="forecasts")
    temporada = relationship("Temporada", back_populates="forecasts")


class Venta(Base):
    __tablename__ = "ventas"
    id                   = Column(Integer, primary_key=True)
    sku                  = Column(String(50), ForeignKey("productos.sku"), nullable=False)
    fecha                = Column(Date, nullable=False)
    canal                = Column(String(100))
    fuente               = Column(String(10))
    estado_orden         = Column(String(20))
    estado_despacho      = Column(String(50))
    tipo_linea           = Column(String(20))
    cantidad             = Column(Integer, nullable=False)
    unidades_devueltas   = Column(Integer, nullable=False, default=0)
    precio_total_bruto   = Column(Numeric(12, 2))
    valor_unitario_bruto = Column(Numeric(12, 2))
    costo_unitario_clp   = Column(Numeric(12, 2))
    margen_clp           = Column(Numeric(12, 2))
    margen_pct           = Column(Numeric(6, 4))
    descripcion_producto = Column(Text)
    categoria_erp        = Column(String(100))
    marca_erp            = Column(String(100))
    id_externo           = Column(String(150), unique=True)   # clave del ERP para idempotencia
    activo               = Column(Boolean, default=True)       # FALSE = anulada/devuelta
    created_at           = Column(DateTime, server_default=func.now())

    producto = relationship("Producto", back_populates="ventas")


class Stock(Base):
    __tablename__ = "stock"
    sku                 = Column(String(50), ForeignKey("productos.sku"), primary_key=True)
    stock_base          = Column(Integer, nullable=False, default=0)   # stock físico en bodega
    stock_jun           = Column(Integer, nullable=False, default=0)   # alias stock_base al inicio de jun
    stock_full_ml       = Column(Integer, nullable=False, default=0)   # en depósito Mercado Libre
    stock_full_fala     = Column(Integer, nullable=False, default=0)   # en depósito Falabella
    bodega_transito     = Column(Integer, nullable=False, default=0)   # contenedor en tránsito
    eta_transito        = Column(Date)
    por_arribar         = Column(Integer, nullable=False, default=0)   # OC confirmada, no embarcada
    eta_arribar         = Column(Date)
    pi                  = Column(Integer, nullable=False, default=0)   # proforma invoice pendiente
    eta_pi              = Column(Date)
    fecha_actualizacion = Column(Date, server_default=func.current_date())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())

    producto = relationship("Producto", back_populates="stock")
