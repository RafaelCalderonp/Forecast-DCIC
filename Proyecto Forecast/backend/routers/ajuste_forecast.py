# routers/ajuste_forecast.py
# ──────────────────────────────────────────────────────────────────
# Módulo de ajuste de forecast basado en las últimas 6 semanas de ventas
# ──────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text, literal
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel

from database import get_db
from models.models import Producto, Venta, Forecast, Temporada

router = APIRouter()

# ─── Constantes ──────────────────────────────────────────────────
SEMANAS_MES = 4.333          # semanas promedio por mes
LEAD_TIME_MIN = 90           # días mínimos para recibir mercadería
LEAD_TIME_MAX = 120          # días máximos

# Índices de estacionalidad para Verano/Rotativo (mes 1..12)
# Base = 1.0 (No Estacional). Verano pico = 1.4
INDICES_VR = {
    1: 1.40, 2: 1.30, 3: 0.90, 4: 0.80,
    5: 0.70, 6: 0.65, 7: 0.75, 8: 0.85,
    9: 1.00, 10: 1.10, 11: 1.25, 12: 1.35,
}

NOMBRES_MES = {
    1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril',
    5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto',
    9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre',
}

# ─── Utilidades de temporada ──────────────────────────────────────

def meses_activos(temporada: str) -> set:
    """Meses del año donde el producto tiene actividad."""
    if temporada == 'Verano':
        return {9, 10, 11, 12, 1, 2}
    if temporada == 'Invierno':
        return {3, 4, 5, 6, 7, 8}
    return set(range(1, 13))   # No Estacional y Verano/Rotativo → todo el año


def en_temporada_activa(temporada: str, mes: int) -> bool:
    return mes in meses_activos(temporada)


def horizonte_proyeccion(fecha_corte: date, temporada: str) -> List[tuple]:
    """
    Retorna lista de (anio, mes) a proyectar desde el mes siguiente
    a fecha_corte, respetando la temporada del producto.

    Reglas:
    - Verano       → próxima temporada Sep-Feb (puede cruzar año)
    - Invierno     → resto de la temporada Mar-Ago del año en curso
    - No Estacional / Verano-Rotativo → resto del año en curso
    """
    mes_inicio = fecha_corte.month + 1
    anio_inicio = fecha_corte.year
    if mes_inicio > 12:
        mes_inicio = 1
        anio_inicio += 1

    meses = []

    if temporada == 'Verano':
        # Próxima temporada: Sep año_actual → Feb año_actual+1
        # Si ya pasamos Sep del año actual, la próxima es Sep año+1
        if fecha_corte.month < 9:
            inicio_temporada = (fecha_corte.year, 9)
        else:
            inicio_temporada = (fecha_corte.year + 1, 9)

        anio_t, mes_t = inicio_temporada
        for _ in range(6):        # Sep, Oct, Nov, Dic, Ene, Feb
            meses.append((anio_t, mes_t))
            mes_t += 1
            if mes_t > 12:
                mes_t = 1
                anio_t += 1

    elif temporada == 'Invierno':
        # Resto de la temporada Mar-Ago del año en curso
        for mes in range(mes_inicio, 9):   # hasta Agosto inclusive
            if mes < 1:
                continue
            meses.append((fecha_corte.year, mes))

    else:
        # No Estacional / Verano-Rotativo → resto del año en curso
        for mes in range(mes_inicio, 13):
            meses.append((fecha_corte.year, mes))

    return meses


def proyectar_cantidad(weekly_avg: float, anio: int, mes: int,
                       temporada: str,
                       mes_actual: int) -> int:
    """
    Calcula la cantidad proyectada para un mes dado.
    Para Verano/Rotativo aplica índice de estacionalidad relativo al mes actual.
    """
    if temporada == 'Verano/Rotativo':
        idx_actual = INDICES_VR.get(mes_actual, 1.0)
        idx_futuro = INDICES_VR.get(mes, 1.0)
        factor = idx_futuro / idx_actual if idx_actual > 0 else 1.0
        return max(0, round(weekly_avg * SEMANAS_MES * factor))

    return max(0, round(weekly_avg * SEMANAS_MES))


def puede_comprar_a_tiempo(fecha_corte: date, anio: int, mes: int,
                           lead_time: int = LEAD_TIME_MIN) -> bool:
    """True si haciendo la OC hoy, la mercadería llega antes del inicio del mes."""
    inicio_mes = date(anio, mes, 1)
    return (fecha_corte + timedelta(days=lead_time)) <= inicio_mes


# ─── Schemas de respuesta ─────────────────────────────────────────

class MesProyeccion(BaseModel):
    anio: int
    mes: int
    nombre_mes: str
    forecast_actual: int
    proyeccion: int
    diferencia: int          # proyeccion − forecast_actual
    puede_comprar: bool      # ¿llega a tiempo con lead time mínimo?


class ProyeccionSKU(BaseModel):
    sku: str
    descripcion: Optional[str]
    temporada: str
    en_temporada_activa: bool
    ventas_6s_bruto: int
    ventas_6s_neto: int      # bruto − devoluciones
    semanas_con_datos: int   # cuántas de las 6 semanas tuvieron ventas
    weekly_avg_neto: float
    proyecciones: List[MesProyeccion]
    advertencia: Optional[str] = None


class AplicarItem(BaseModel):
    sku: str
    anio: int
    mes: int
    cantidad: int


class AplicarResultado(BaseModel):
    sku: str
    anio: int
    mes: int
    cantidad_anterior: int
    cantidad_nueva: int
    accion: str   # "creado" | "actualizado" | "sin_cambio"


# ─── Endpoint: Calcular proyección ───────────────────────────────

@router.get("/proyeccion", response_model=List[ProyeccionSKU])
async def calcular_proyeccion(
    fecha_corte: Optional[date] = Query(default=None, description="Fecha base (default: hoy)"),
    sku: Optional[str] = Query(default=None, description="Filtrar por SKU específico"),
    temporada_nombre: Optional[str] = Query(default=None, description="Filtrar por temporada"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula la proyección de forecast para cada SKU basándose en
    las últimas 6 semanas de ventas netas (cantidad − devoluciones).

    Reglas por temporada:
    - Verano         → proyecta próxima temporada Sep-Feb
    - Invierno       → proyecta meses restantes Mar-Ago del año actual
    - No Estacional  → proyecta meses restantes del año actual
    - Verano/Rotativo→ proyecta meses restantes con índice estacional
    """
    if fecha_corte is None:
        from datetime import datetime
        fecha_corte = datetime.today().date()

    fecha_desde = fecha_corte - timedelta(weeks=6)

    # Cargar productos con temporada
    q_prod = (
        select(Producto, Temporada)
        .join(Temporada, Producto.temporada_id == Temporada.id, isouter=True)
        .where(Producto.activo == True)
    )
    if sku:
        q_prod = q_prod.where(Producto.sku == sku)
    if temporada_nombre:
        q_prod = q_prod.where(Temporada.nombre == temporada_nombre)

    result = await db.execute(q_prod)
    filas_prod = result.all()

    if not filas_prod:
        return []

    skus = [p.sku for p, _ in filas_prod]

    # Ventas últimas 6 semanas — agrupadas por SKU y semana
    q_ventas = (
        select(
            Venta.sku,
            func.date_trunc(text("'week'"), Venta.fecha).label('semana'),
            func.sum(Venta.cantidad).label('bruto'),
            func.sum(Venta.unidades_devueltas).label('devueltas'),
        )
        .where(Venta.sku.in_(skus))
        .where(Venta.fecha >= fecha_desde)
        .where(Venta.fecha <= fecha_corte)
        .group_by(Venta.sku, func.date_trunc(text("'week'"), Venta.fecha))
    )
    ventas_result = await db.execute(q_ventas)
    ventas_rows = ventas_result.all()

    # Agrupar ventas por SKU
    ventas_por_sku: dict[str, dict] = {}
    for row in ventas_rows:
        s = row.sku
        if s not in ventas_por_sku:
            ventas_por_sku[s] = {'bruto': 0, 'devueltas': 0, 'semanas': 0}
        ventas_por_sku[s]['bruto']    += (row.bruto or 0)
        ventas_por_sku[s]['devueltas'] += (row.devueltas or 0)
        ventas_por_sku[s]['semanas']  += 1

    # Forecast actual para los SKUs — cargamos todo de una vez
    q_fc = select(Forecast).where(Forecast.sku.in_(skus))
    fc_result = await db.execute(q_fc)
    fc_rows = fc_result.scalars().all()
    fc_map: dict[tuple, int] = {(f.sku, f.anio, f.mes): f.cantidad for f in fc_rows}

    # Construir proyecciones
    proyecciones: List[ProyeccionSKU] = []

    for producto, temporada in filas_prod:
        temp_nombre = temporada.nombre if temporada else 'No Estacional'
        datos_v = ventas_por_sku.get(producto.sku, {'bruto': 0, 'devueltas': 0, 'semanas': 0})

        ventas_bruto  = datos_v['bruto']
        ventas_devuel = datos_v['devueltas']
        ventas_neto   = ventas_bruto - ventas_devuel
        semanas_datos = datos_v['semanas']

        # Promedio semanal neto sobre 6 semanas (no solo semanas con venta,
        # para reflejar semanas sin ventas como demanda real)
        weekly_avg = ventas_neto / 6.0

        horizonte  = horizonte_proyeccion(fecha_corte, temp_nombre)
        mes_actual = fecha_corte.month

        activa = en_temporada_activa(temp_nombre, mes_actual)

        meses_proy: List[MesProyeccion] = []
        for (anio, mes) in horizonte:
            fc_actual  = fc_map.get((producto.sku, anio, mes), 0)
            proyeccion = proyectar_cantidad(weekly_avg, anio, mes, temp_nombre, mes_actual)
            diferencia = proyeccion - fc_actual
            comprar    = puede_comprar_a_tiempo(fecha_corte, anio, mes)

            meses_proy.append(MesProyeccion(
                anio=anio,
                mes=mes,
                nombre_mes=NOMBRES_MES[mes],
                forecast_actual=fc_actual,
                proyeccion=proyeccion,
                diferencia=diferencia,
                puede_comprar=comprar,
            ))

        # Advertencias automáticas
        advertencia = None
        if ventas_neto == 0 and temp_nombre in ('Verano', 'Invierno'):
            if activa:
                advertencia = "Sin ventas en temporada activa. Verificar quiebre de stock o descontinuado."
            else:
                advertencia = "Producto fuera de temporada. Proyección basada en historial 0 — revisar manualmente."
        elif semanas_datos < 3:
            advertencia = f"Solo {semanas_datos} semana(s) con datos en las últimas 6 semanas. Proyección poco representativa."

        proyecciones.append(ProyeccionSKU(
            sku=producto.sku,
            descripcion=producto.descripcion,
            temporada=temp_nombre,
            en_temporada_activa=activa,
            ventas_6s_bruto=ventas_bruto,
            ventas_6s_neto=ventas_neto,
            semanas_con_datos=semanas_datos,
            weekly_avg_neto=round(weekly_avg, 2),
            proyecciones=meses_proy,
            advertencia=advertencia,
        ))

    return proyecciones


# ─── Endpoint: Aplicar proyección al forecast ─────────────────────

@router.post("/aplicar-proyeccion", response_model=List[AplicarResultado])
async def aplicar_proyeccion(
    items: List[AplicarItem],
    db: AsyncSession = Depends(get_db)
):
    """
    Aplica (upsert) los valores de proyección al forecast.
    Registra si cada fila fue creada, actualizada o no cambió.
    """
    if not items:
        raise HTTPException(400, "Lista de items vacía")

    resultados: List[AplicarResultado] = []

    for item in items:
        q = select(Forecast).where(
            and_(
                Forecast.sku == item.sku,
                Forecast.anio == item.anio,
                Forecast.mes == item.mes,
            )
        )
        existente = (await db.execute(q)).scalar_one_or_none()

        if existente:
            anterior = existente.cantidad
            if anterior == item.cantidad:
                accion = "sin_cambio"
            else:
                existente.cantidad = item.cantidad
                accion = "actualizado"
            resultados.append(AplicarResultado(
                sku=item.sku, anio=item.anio, mes=item.mes,
                cantidad_anterior=anterior,
                cantidad_nueva=item.cantidad,
                accion=accion,
            ))
        else:
            nuevo = Forecast(
                sku=item.sku,
                anio=item.anio,
                mes=item.mes,
                cantidad=item.cantidad,
            )
            db.add(nuevo)
            resultados.append(AplicarResultado(
                sku=item.sku, anio=item.anio, mes=item.mes,
                cantidad_anterior=0,
                cantidad_nueva=item.cantidad,
                accion="creado",
            ))

    await db.commit()
    return resultados


# ─── Endpoint: Resumen de alertas de quiebre potencial ───────────

class AlertaQuiebre(BaseModel):
    sku: str
    descripcion: Optional[str]
    temporada: str
    semanas_restantes_stock: Optional[float]
    stock_total: int
    weekly_avg_neto: float
    puede_comprar: bool
    meses_sin_stock: List[str]
    nivel: str   # "CRITICO" | "ADVERTENCIA" | "OK"


@router.get("/alertas-quiebre", response_model=List[AlertaQuiebre])
async def alertas_quiebre(
    fecha_corte: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """
    Detecta productos que podrían quedarse sin stock durante su temporada
    considerando el lead time de 90-120 días.
    """
    if fecha_corte is None:
        from datetime import datetime
        fecha_corte = datetime.today().date()

    fecha_desde = fecha_corte - timedelta(weeks=6)

    # Productos + temporada + stock
    from models.models import Stock
    q = (
        select(Producto, Temporada, Stock)
        .join(Temporada, Producto.temporada_id == Temporada.id, isouter=True)
        .join(Stock, Stock.sku == Producto.sku, isouter=True)
        .where(Producto.activo == True)
    )
    rows = (await db.execute(q)).all()

    skus = [p.sku for p, _, _ in rows]

    # Ventas últimas 6 semanas
    q_v = (
        select(
            Venta.sku,
            func.sum(Venta.cantidad - Venta.unidades_devueltas).label('neto')
        )
        .where(Venta.sku.in_(skus))
        .where(Venta.fecha.between(fecha_desde, fecha_corte))
        .group_by(Venta.sku)
    )
    v_rows = (await db.execute(q_v)).all()
    ventas_map = {r.sku: (r.neto or 0) for r in v_rows}

    alertas: List[AlertaQuiebre] = []

    for producto, temporada, stock in rows:
        temp_nombre = temporada.nombre if temporada else 'No Estacional'

        # Stock total disponible hoy
        stock_total = 0
        if stock:
            stock_total = (
                stock.stock_base + stock.stock_full_ml + stock.stock_full_fala +
                stock.bodega_transito + stock.por_arribar + stock.pi
            )

        ventas_neto_6s = ventas_map.get(producto.sku, 0)
        weekly_avg     = ventas_neto_6s / 6.0

        # Semanas de stock restantes
        if weekly_avg > 0:
            semanas_restantes = stock_total / weekly_avg
        else:
            semanas_restantes = None   # sin datos de venta

        # Horizonte de temporada activa
        horizonte = horizonte_proyeccion(fecha_corte, temp_nombre)

        # Simular consumo de stock mes a mes
        stock_simulado = stock_total
        meses_sin_stock = []
        for (anio, mes) in horizonte:
            demanda_mes = proyectar_cantidad(weekly_avg, anio, mes, temp_nombre, fecha_corte.month)
            stock_simulado -= demanda_mes
            if stock_simulado < 0:
                # ¿Se puede reponer a tiempo?
                puede = puede_comprar_a_tiempo(fecha_corte, anio, mes)
                if not puede or temp_nombre in ('Verano', 'Invierno'):
                    meses_sin_stock.append(f"{NOMBRES_MES[mes]} {anio}")
                stock_simulado = 0   # no acumula negativo

        puede_comprar_hoy = puede_comprar_a_tiempo(fecha_corte, horizonte[0][0], horizonte[0][1]) if horizonte else False

        # Nivel de alerta
        if meses_sin_stock:
            nivel = "CRITICO" if temp_nombre in ('Verano', 'Invierno') else "ADVERTENCIA"
        elif semanas_restantes is not None and semanas_restantes < 8:
            nivel = "ADVERTENCIA"
        else:
            nivel = "OK"

        if nivel != "OK":   # solo retornar los que tienen problema
            alertas.append(AlertaQuiebre(
                sku=producto.sku,
                descripcion=producto.descripcion,
                temporada=temp_nombre,
                semanas_restantes_stock=round(semanas_restantes, 1) if semanas_restantes is not None else None,
                stock_total=stock_total,
                weekly_avg_neto=round(weekly_avg, 2),
                puede_comprar=puede_comprar_hoy,
                meses_sin_stock=meses_sin_stock,
                nivel=nivel,
            ))

    # Ordenar: CRITICO primero
    alertas.sort(key=lambda a: (0 if a.nivel == 'CRITICO' else 1, a.sku))
    return alertas


@router.get("/alertas-descontinuar")
async def alertas_descontinuar(db: AsyncSession = Depends(get_db)):
    """Productos marcados 'Descontinuar' con stock = 0 — candidatos a dar de baja."""
    result = await db.execute(text("""
        SELECT p.sku, p.descripcion,
               COALESCE(s.stock_jun,0)
               + COALESCE(s.llegada_jun,0) + COALESCE(s.llegada_jul,0)
               + COALESCE(s.llegada_ago,0) + COALESCE(s.llegada_sep,0)
               + COALESCE(s.llegada_oct,0) + COALESCE(s.llegada_nov,0)
               + COALESCE(s.llegada_dic,0) AS stock_total,
               m.nombre AS marca
        FROM productos p
        LEFT JOIN stock s ON s.sku = p.sku
        LEFT JOIN marcas m ON m.id = p.marca_id
        WHERE p.comentario = 'Descontinuar'
          AND p.activo = TRUE
          AND (
            COALESCE(s.stock_jun,0)
            + COALESCE(s.llegada_jun,0) + COALESCE(s.llegada_jul,0)
            + COALESCE(s.llegada_ago,0) + COALESCE(s.llegada_sep,0)
            + COALESCE(s.llegada_oct,0) + COALESCE(s.llegada_nov,0)
            + COALESCE(s.llegada_dic,0)
          ) = 0
        ORDER BY p.sku
    """))
    rows = result.mappings().all()
    return [{"sku": r["sku"], "descripcion": r["descripcion"],
             "stock_total": int(r["stock_total"]), "marca": r["marca"]} for r in rows]
