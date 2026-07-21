# schemas/schemas.py - Pydantic v2 schemas

from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


# ─── TEMPORADAS ───────────────────────────────────────────
class TemporadaBase(BaseModel):
    nombre: str
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    activa: bool = True

class TemporadaCreate(TemporadaBase): pass
class TemporadaOut(TemporadaBase):
    id: int
    class Config: from_attributes = True


# ─── MARCAS ───────────────────────────────────────────────
class MarcaBase(BaseModel):
    nombre: str

class MarcaCreate(MarcaBase): pass
class MarcaOut(MarcaBase):
    id: int
    class Config: from_attributes = True


# ─── CATEGORIAS ───────────────────────────────────────────
class CategoriaBase(BaseModel):
    nombre: str

class CategoriaCreate(CategoriaBase): pass
class CategoriaOut(CategoriaBase):
    id: int
    class Config: from_attributes = True


# ─── SUBCATEGORIAS ────────────────────────────────────────
class SubcategoriaOut(BaseModel):
    id: int
    nombre: str
    class Config: from_attributes = True


# ─── PRODUCTOS ────────────────────────────────────────────
class ProductoBase(BaseModel):
    sku: str
    marca_id: int
    categoria_id: int
    temporada_id: Optional[int] = None
    descripcion: Optional[str] = None
    precio_venta_bruto: Decimal = Decimal("0")
    precio_venta_neto: Decimal = Decimal("0")
    activo: bool = True
    por_discontinuar: bool = False

class ProductoCreate(ProductoBase): pass
class ProductoUpdate(BaseModel):
    marca_id: Optional[int] = None
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    temporada_id: Optional[int] = None
    descripcion: Optional[str] = None
    precio_venta_bruto: Optional[Decimal] = None
    precio_venta_neto: Optional[Decimal] = None
    costo_unitario_neto: Optional[Decimal] = None
    activo: Optional[bool] = None
    por_discontinuar: Optional[bool] = None
    comentario: Optional[str] = None
    tipo_producto: Optional[str] = None
    grupo_pareto: Optional[str] = None

class ProductoOut(ProductoBase):
    comentario: Optional[str] = None
    tipo_producto: Optional[str] = None
    grupo_pareto: Optional[str] = None
    subcategoria_id: Optional[int] = None
    costo_unitario_neto: Optional[Decimal] = None
    por_discontinuar: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    marca: Optional[MarcaOut] = None
    categoria: Optional[CategoriaOut] = None
    subcategoria: Optional[SubcategoriaOut] = None
    temporada: Optional[TemporadaOut] = None
    stock_total: Optional[int] = 0
    class Config: from_attributes = True


# ─── PACKS ────────────────────────────────────────────────
class PackComponenteBase(BaseModel):
    producto_sku: str
    cantidad: int

class PackComponenteOut(PackComponenteBase):
    id: int
    class Config: from_attributes = True

class PackBase(BaseModel):
    sku: str
    marca_id: int
    categoria_id: int
    temporada_id: Optional[int] = None
    descripcion: Optional[str] = None
    precio_venta_bruto: Decimal = Decimal("0")
    precio_venta_neto: Decimal = Decimal("0")
    activo: bool = True

class PackCreate(PackBase):
    componentes: List[PackComponenteBase]

class PackUpdate(BaseModel):
    marca_id: Optional[int] = None
    categoria_id: Optional[int] = None
    temporada_id: Optional[int] = None
    descripcion: Optional[str] = None
    precio_venta_bruto: Optional[Decimal] = None
    precio_venta_neto: Optional[Decimal] = None
    activo: Optional[bool] = None
    componentes: Optional[List[PackComponenteBase]] = None

class PackOut(PackBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    marca: Optional[MarcaOut] = None
    categoria: Optional[CategoriaOut] = None
    temporada: Optional[TemporadaOut] = None
    componentes: List[PackComponenteOut] = []
    class Config: from_attributes = True


# ─── FORECAST ─────────────────────────────────────────────
class ForecastBase(BaseModel):
    sku: str
    temporada_id: Optional[int] = None
    anio: int
    mes: int
    cantidad: int = 0

    @field_validator("mes")
    @classmethod
    def validar_mes(cls, v):
        if not 1 <= v <= 12:
            raise ValueError("Mes debe estar entre 1 y 12")
        return v

class ForecastCreate(ForecastBase): pass
class ForecastUpdate(BaseModel):
    cantidad: int

class ForecastOut(ForecastBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config: from_attributes = True

# Vista pivot: SKU + array de 12 meses
class ForecastPivotRow(BaseModel):
    sku: str
    anio: int
    meses: List[int]  # índice 0=Enero ... 11=Diciembre


# ─── VENTAS ───────────────────────────────────────────────
class VentaBase(BaseModel):
    sku:                  str
    fecha:                date
    canal:                Optional[str]     = None
    cantidad:             int
    unidades_devueltas:   int               = 0
    precio_total_bruto:   Optional[Decimal] = None
    valor_unitario_neto:  Optional[Decimal] = None
    costo_unitario_clp:   Optional[Decimal] = None
    margen_clp:           Optional[Decimal] = None
    margen_pct:           Optional[Decimal] = None
    descripcion_producto: Optional[str]     = None
    categoria_erp:        Optional[str]     = None
    marca_erp:            Optional[str]     = None

class VentaCreate(VentaBase): pass

class VentaUpsert(VentaBase):
    """Para integración ERP — requiere id_externo para garantizar idempotencia."""
    id_externo:   str            # clave única del ERP (orden_id, linea_id, etc.)
    fuente:       str = "erp"   # origen del dato para trazabilidad
    estado_orden: Optional[str] = "Regular"  # Regular | Anulada | Devuelta

class VentaOut(VentaBase):
    id:            int
    cantidad_neta: int = 0        # calculado: cantidad - unidades_devueltas
    created_at:    Optional[datetime] = None

    @classmethod
    def model_validate(cls, obj, **kw):
        instance = super().model_validate(obj, **kw)
        instance.cantidad_neta = instance.cantidad - instance.unidades_devueltas
        return instance

    class Config: from_attributes = True


# ─── STOCK ────────────────────────────────────────────────
class StockBase(BaseModel):
    sku: str
    stock_base: int = 0
    stock_full_ml: int = 0
    stock_full_fala: int = 0
    bodega_transito: int = 0
    por_arribar: int = 0
    pi: int = 0
    eta_transito: Optional[date] = None
    eta_arribar: Optional[date] = None
    eta_pi: Optional[date] = None
    fecha_actualizacion: Optional[date] = None

class StockCreate(StockBase): pass
class StockUpdate(BaseModel):
    stock_base: Optional[int] = None
    stock_full_ml: Optional[int] = None
    stock_full_fala: Optional[int] = None
    bodega_transito: Optional[int] = None
    por_arribar: Optional[int] = None
    pi: Optional[int] = None
    eta_transito: Optional[date] = None
    eta_arribar: Optional[date] = None
    eta_pi: Optional[date] = None
    fecha_actualizacion: Optional[date] = None

class StockOut(StockBase):
    stock_total: int = 0   # calculado: base + ml + fala + transito + por_arribar + pi
    updated_at: Optional[datetime] = None
    class Config: from_attributes = True
