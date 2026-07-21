# routers/ventas.py
import subprocess, sys, os, calendar, hashlib, uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, text
from typing import List, Optional
from datetime import date
from pydantic import BaseModel
from database import get_db, AsyncSessionLocal
from models.models import Venta
from schemas.schemas import VentaCreate, VentaOut, VentaUpsert
from auth import require_api_key, require_rol
from logger import get_logger

log = get_logger("forecast_dcic.ventas")

router = APIRouter()


@router.get("/resumen")
async def resumen_ventas(
    anio:        Optional[int] = Query(None),
    mes:         Optional[int] = Query(None),
    sku:         Optional[str] = Query(None),
    canal:       Optional[str] = Query(None),
    marca_id:    Optional[int] = Query(None),
    categoria_id:Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Ventas agrupadas por SKU + año + mes con descripción, precio y margen."""
    params: dict = {}
    where_parts = ["v.estado_orden = 'Regular'"]
    if anio:
        where_parts.append("EXTRACT(YEAR FROM v.fecha) = :anio")
        params["anio"] = anio
    if mes:
        where_parts.append("EXTRACT(MONTH FROM v.fecha) = :mes")
        params["mes"] = mes
    if sku:
        where_parts.append("(v.sku ILIKE :sku OR p.descripcion ILIKE :sku)")
        params["sku"] = f"%{sku}%"
    if canal:
        where_parts.append("v.canal = :canal")
        params["canal"] = canal
    if marca_id:
        where_parts.append("p.marca_id = :marca_id")
        params["marca_id"] = marca_id
    if categoria_id:
        where_parts.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    where_sql = "WHERE " + " AND ".join(where_parts)

    sql = f"""
    SELECT
        v.sku,
        p.descripcion,
        m.nombre  AS marca,
        c.nombre  AS categoria,
        EXTRACT(YEAR  FROM v.fecha)::int AS anio,
        EXTRACT(MONTH FROM v.fecha)::int AS mes,
        v.canal,
        SUM(v.cantidad - v.unidades_devueltas)                            AS cantidad_neta,
        ROUND(AVG(v.precio_total_bruto)::numeric, 0)                      AS precio_total_bruto,
        ROUND(AVG(v.valor_unitario_bruto)::numeric, 0)                    AS precio_venta_bruto,
        ROUND(SUM(COALESCE(v.precio_total_bruto, 0))::numeric, 0)         AS venta_bruta_total,
        ROUND(SUM(COALESCE(v.precio_total_bruto, 0)) / 1.19::numeric, 0)  AS venta_neta_total,
        ROUND(SUM(COALESCE(v.margen_clp, 0))::numeric, 0)                 AS margen_total,
        CASE
            WHEN SUM(COALESCE(v.precio_total_bruto, 0)) > 0
            THEN ROUND(
                SUM(COALESCE(v.margen_clp, 0)) * 100.0
                / SUM(COALESCE(v.precio_total_bruto, 0)) * 1.19, 1)
            ELSE 0
        END AS margen_pct
    FROM ventas v
    LEFT JOIN productos p ON p.sku = v.sku
    LEFT JOIN marcas     m ON m.id = p.marca_id
    LEFT JOIN categorias c ON c.id = p.categoria_id
    {where_sql}
    GROUP BY v.sku, p.descripcion, m.nombre, c.nombre,
             EXTRACT(YEAR FROM v.fecha), EXTRACT(MONTH FROM v.fecha), v.canal
    ORDER BY anio DESC, mes DESC, venta_bruta_total DESC
    LIMIT 50000
    """
    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/canales")
async def listar_canales(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text(
        "SELECT DISTINCT canal FROM ventas WHERE canal IS NOT NULL ORDER BY canal"
    ))
    return [r[0] for r in result.fetchall()]

@router.get("/anios")
async def listar_anios(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text(
        "SELECT DISTINCT EXTRACT(YEAR FROM fecha)::int AS anio FROM ventas ORDER BY anio"
    ))
    return [r[0] for r in result.fetchall()]

@router.get("/", response_model=List[VentaOut])
async def listar_ventas(
    sku: Optional[str] = None,
    canal: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(500, ge=1, le=5000, description="Máximo de registros a retornar"),
    db: AsyncSession = Depends(get_db)
):
    q = select(Venta)
    if sku:         q = q.where(Venta.sku == sku)
    if canal:       q = q.where(Venta.canal == canal)
    if fecha_desde: q = q.where(Venta.fecha >= fecha_desde)
    if fecha_hasta: q = q.where(Venta.fecha <= fecha_hasta)
    result = await db.execute(q.order_by(Venta.fecha.desc()).offset(skip).limit(limit))
    return result.scalars().all()

@router.post("/", response_model=VentaOut, status_code=201)
async def registrar_venta(data: VentaCreate, db: AsyncSession = Depends(get_db)):
    nueva = Venta(**data.model_dump())
    db.add(nueva)
    await db.commit()
    await db.refresh(nueva)
    return nueva

@router.post("/bulk", response_model=List[VentaOut], status_code=201)
async def registrar_ventas_bulk(items: List[VentaCreate], db: AsyncSession = Depends(get_db)):
    nuevas = [Venta(**item.model_dump()) for item in items]
    db.add_all(nuevas)
    await db.commit()
    for v in nuevas:
        await db.refresh(v)
    return nuevas

class UpsertBulkResult(BaseModel):
    insertados: int
    actualizados: int
    omitidos_cancelados: int
    errores: List[dict]

@router.post("/upsert-bulk", response_model=UpsertBulkResult, status_code=200)
async def upsert_ventas_bulk(
    items: List[VentaUpsert],
    db: AsyncSession = Depends(get_db),
    _api_key: dict = Depends(require_api_key),
):
    """
    Carga idempotente de ventas desde ERP u otras fuentes externas.

    - Usa id_externo como clave única: reenvíos no generan duplicados.
    - Ventas con estado_orden Anulada o Devuelta se omiten del historial activo
      (se registran con activo=FALSE para auditoría).
    - Retorna conteo de insertados, actualizados, omitidos y errores por fila.
    """
    ESTADOS_EXCLUIR = {"anulada", "devuelta", "cancelada"}
    insertados = actualizados = omitidos = 0
    errores: List[dict] = []

    for item in items:
        try:
            await db.execute(text("SAVEPOINT sp_upsert"))
        except Exception:
            pass

        try:
            estado = (item.estado_orden or "Regular").strip()
            excluir = estado.lower() in ESTADOS_EXCLUIR

            # Verificar si existía antes del upsert para contabilizar insertados/actualizados
            existe = await db.execute(
                text("SELECT 1 FROM ventas WHERE id_externo = :id_ext"),
                {"id_ext": item.id_externo},
            )
            era_existente = existe.fetchone() is not None

            await db.execute(
                text("""
                    INSERT INTO ventas (
                        sku, fecha, canal, cantidad, unidades_devueltas,
                        precio_total_bruto, costo_unitario_clp, margen_clp,
                        estado_orden, fuente, id_externo, activo
                    ) VALUES (
                        :sku, :fecha, :canal, :cantidad, :devueltas,
                        :precio, :costo, :margen, :estado, :fuente, :id_ext, :activo
                    )
                    ON CONFLICT (id_externo) DO UPDATE SET
                        sku = EXCLUDED.sku, fecha = EXCLUDED.fecha, canal = EXCLUDED.canal,
                        cantidad = EXCLUDED.cantidad, unidades_devueltas = EXCLUDED.unidades_devueltas,
                        precio_total_bruto = EXCLUDED.precio_total_bruto,
                        costo_unitario_clp = EXCLUDED.costo_unitario_clp,
                        margen_clp = EXCLUDED.margen_clp, estado_orden = EXCLUDED.estado_orden,
                        fuente = EXCLUDED.fuente, activo = EXCLUDED.activo
                """),
                {
                    "sku": item.sku, "fecha": item.fecha, "canal": item.canal,
                    "cantidad": item.cantidad, "devueltas": item.unidades_devueltas,
                    "precio": item.precio_total_bruto, "costo": item.costo_unitario_clp,
                    "margen": item.margen_clp, "estado": estado,
                    "fuente": item.fuente, "id_ext": item.id_externo,
                    "activo": not excluir,
                },
            )

            if era_existente:
                actualizados += 1
            else:
                insertados += 1

            if excluir:
                omitidos += 1

            await db.execute(text("RELEASE SAVEPOINT sp_upsert"))

        except Exception as exc:
            await db.execute(text("ROLLBACK TO SAVEPOINT sp_upsert"))
            msg = str(exc)
            if "ForeignKeyViolation" in msg or "ventas_sku_fkey" in msg:
                errores.append({"id_externo": item.id_externo, "sku": item.sku, "error": "sku_no_en_productos"})
            else:
                errores.append({"id_externo": item.id_externo, "sku": item.sku, "error": msg[:200]})

    await db.commit()
    log.info(
        f"upsert-bulk fuente={items[0].fuente if items else '?'} "
        f"insertados={insertados} actualizados={actualizados} "
        f"omitidos={omitidos} errores={len(errores)}"
    )
    return UpsertBulkResult(
        insertados=insertados,
        actualizados=actualizados,
        omitidos_cancelados=omitidos,
        errores=errores,
    )


class SyncRequest(BaseModel):
    desde: date
    hasta: date
    fuente: Optional[str] = None  # "bsale" | "wivo" | None = ambas

@router.post("/sync")
async def sync_ventas(req: SyncRequest):
    """Lanza sync_ventas.py en background y retorna estado inicial."""
    script = os.path.join(os.path.dirname(__file__), '..', 'sync_ventas.py')
    script = os.path.normpath(script)
    if not os.path.exists(script):
        raise HTTPException(500, "sync_ventas.py no encontrado")
    cmd = [sys.executable, script,
           '--desde', str(req.desde),
           '--hasta',  str(req.hasta)]
    if req.fuente:
        cmd += ['--fuente', req.fuente]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=os.path.dirname(script)
        )
        # Esperar máx 120 segundos y retornar lo que haya
        try:
            out, _ = proc.communicate(timeout=120)
            return {"ok": proc.returncode == 0, "salida": out[-4000:]}
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            return {"ok": False, "salida": out[-4000:] + "\n[TIMEOUT: proceso terminado]"}
    except Exception as e:
        raise HTTPException(500, str(e))

class SyncErpChunkedRequest(BaseModel):
    desde:   date
    hasta:   date
    fuente:  str = "all"   # "bsale" | "wivo" | "all"
    resync:  bool = False   # True = borrar período y reinsertar desde cero


def _id_externo_row(row: dict, idx: int) -> str:
    num_pedido   = row.get("num_pedido") or ""
    num_suborden = row.get("num_suborden") or ""
    if num_pedido and num_suborden:
        return f"{num_pedido}-{num_suborden}"
    if num_pedido:
        return f"{num_pedido}-{idx}"
    fuente = row.get("fuente") or "erp"
    fecha  = row.get("fecha") or "0000-00-00"
    sku    = row.get("sku_id") or row.get("sku") or "NOSKU"
    canal  = (row.get("canal") or "").replace(" ", "_")
    raw    = f"{fuente}-{fecha}-{sku}-{canal}-{idx}"
    return raw


@router.post("/sync-erp-chunked", dependencies=[Depends(require_rol("admin", "editor"))])
async def sync_erp_chunked(req: SyncErpChunkedRequest, db: AsyncSession = Depends(get_db)):
    """
    Sincroniza ventas del ERP externo iterando mes a mes por fuente.
    Retorna resumen estructurado + lista de SKUs que no existen en productos.
    """
    try:
        import httpx
    except ImportError:
        raise HTTPException(500, "httpx no instalado: pip install httpx")

    ERP_URL = os.getenv("ERP_API_URL", "https://dcic-api-production.up.railway.app")
    ERP_KEY = os.getenv("ERP_API_KEY", "")
    ERP_HEADERS = {"X-API-Key": ERP_KEY} if ERP_KEY else {}
    fuentes = ["bsale", "wivo"] if req.fuente == "all" else [req.fuente]
    ESTADOS_EXCLUIR = {"anulada", "devuelta", "cancelada"}

    # Chunks mensuales
    chunks: list[tuple[date, date]] = []
    cur = req.desde.replace(day=1)
    while cur <= req.hasta:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        fin = min(date(cur.year, cur.month, last_day), req.hasta)
        chunks.append((cur, fin))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

    totales = {"insertados": 0, "actualizados": 0, "omitidos": 0,
               "errores_fk": 0, "errores_otros": 0, "sin_sku": 0}
    skus_faltantes: dict[str, dict] = {}   # sku → info ERP

    # Borrar el rango completo antes de insertar (garantía anti-duplicados)
    deleted = await db.execute(
        text("DELETE FROM ventas WHERE fecha BETWEEN :d AND :h"),
        {"d": req.desde, "h": req.hasta}
    )
    await db.commit()
    log.info(f"sync-erp-chunked: deleted {deleted.rowcount} rows for {req.desde}→{req.hasta}")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        for fuente in fuentes:
            for desde_c, hasta_c in chunks:
                offset = 0
                while True:
                    params = {"fecha_desde": str(desde_c), "fecha_hasta": str(hasta_c),
                              "fuente": fuente, "limit": 100, "offset": offset}
                    try:
                        r = await client.get(f"{ERP_URL}/ventas/", params=params, headers=ERP_HEADERS)
                        r.raise_for_status()
                        data = r.json()
                        filas = data if isinstance(data, list) else \
                            (data.get("data") or data.get("items") or data.get("ventas") or [])
                    except Exception as e:
                        log.warning(f"ERP fetch error {fuente} {desde_c}: {e}")
                        break

                    if not filas:
                        break

                    for idx, row in enumerate(filas):
                        sku = row.get("sku_id") or row.get("sku") or ""
                        if not sku:
                            totales["sin_sku"] += 1
                            continue

                        estado   = (row.get("estado_orden") or "Regular").strip()
                        excluir  = estado.lower() in ESTADOS_EXCLUIR
                        cantidad = int(row.get("cantidad") or 0)
                        devueltas = cantidad if estado.lower() in {"devuelta", "devueltas"} else 0
                        id_ext   = _id_externo_row(row, offset + idx)

                        try:
                            await db.execute(text("SAVEPOINT sp_chunk"))
                        except Exception:
                            pass

                        try:
                            await db.execute(text("""
                                INSERT INTO ventas (sku,fecha,canal,cantidad,unidades_devueltas,
                                    precio_total_bruto,costo_unitario_clp,margen_clp,
                                    estado_orden,fuente,id_externo,activo,
                                    descripcion_producto,categoria_erp,marca_erp,
                                    num_pedido,num_suborden)
                                VALUES (:sku,:fecha,:canal,:qty,:dev,
                                    :precio,:costo,:margen,
                                    :estado,:fuente,:ie,:activo,
                                    :desc,:cat,:marca,:n_orden,:n_pedido)
                                ON CONFLICT (id_externo) DO UPDATE SET
                                    sku=EXCLUDED.sku, fecha=EXCLUDED.fecha, canal=EXCLUDED.canal,
                                    cantidad=EXCLUDED.cantidad, precio_total_bruto=EXCLUDED.precio_total_bruto,
                                    costo_unitario_clp=EXCLUDED.costo_unitario_clp,
                                    margen_clp=EXCLUDED.margen_clp, estado_orden=EXCLUDED.estado_orden,
                                    fuente=EXCLUDED.fuente, activo=EXCLUDED.activo
                            """), {
                                "sku": sku, "fecha": row.get("fecha"), "canal": row.get("canal"),
                                "qty": cantidad, "dev": devueltas,
                                "precio": row.get("venta_bruto"), "costo": row.get("costo_unitario_neto"),
                                "margen": row.get("margen_clp"), "estado": estado,
                                "fuente": fuente, "ie": id_ext, "activo": not excluir,
                                "desc": row.get("desc_producto"), "cat": row.get("categoria_producto"),
                                "marca": row.get("marca_producto"),
                                "n_orden": row.get("n_orden"), "n_pedido": row.get("n_pedido"),
                            })
                            if excluir:
                                totales["omitidos"] += 1
                            else:
                                totales["insertados"] += 1

                            await db.execute(text("RELEASE SAVEPOINT sp_chunk"))

                        except Exception as exc:
                            await db.execute(text("ROLLBACK TO SAVEPOINT sp_chunk"))
                            msg = str(exc)
                            if "ventas_sku_fkey" in msg or "ForeignKeyViolation" in msg:
                                totales["errores_fk"] += 1
                                if sku not in skus_faltantes:
                                    skus_faltantes[sku] = {
                                        "sku":        sku,
                                        "descripcion": row.get("desc_producto") or "",
                                        "categoria":   row.get("categoria_producto") or "",
                                        "marca":       row.get("marca_producto") or "",
                                        "canal":       row.get("canal") or "",
                                        "n_ventas":    0,
                                        "venta_bruta": 0.0,
                                    }
                                skus_faltantes[sku]["n_ventas"] += 1
                                skus_faltantes[sku]["venta_bruta"] += float(row.get("venta_bruto") or 0)
                            else:
                                totales["errores_otros"] += 1

                    await db.commit()
                    offset += len(filas)
                    if len(filas) < 100:
                        break

    faltantes_list = sorted(skus_faltantes.values(), key=lambda x: -x["venta_bruta"])
    log.info(
        f"sync-erp-chunked {req.desde}→{req.hasta} fuente={req.fuente} "
        f"ins={totales['insertados']} upd={totales['actualizados']} "
        f"fk={totales['errores_fk']} skus_faltantes={len(faltantes_list)}"
    )
    return {
        "ok": True,
        "resumen": totales,
        "meses_procesados": len(chunks),
        "fuentes": fuentes,
        "skus_faltantes": faltantes_list,
    }


@router.get("/skus-faltantes")
async def skus_faltantes(db: AsyncSession = Depends(get_db)):
    """SKUs con ventas registradas que no existen en la tabla productos."""
    rows = await db.execute(text("""
        SELECT v.sku,
               MAX(v.descripcion_producto) AS descripcion,
               MAX(v.categoria_erp)        AS categoria,
               MAX(v.marca_erp)            AS marca,
               COUNT(*)                    AS n_ventas,
               COALESCE(SUM(v.precio_total_bruto * v.cantidad), 0) AS venta_bruta
        FROM ventas v
        WHERE NOT EXISTS (SELECT 1 FROM productos p WHERE p.sku = v.sku)
          AND v.activo = TRUE
        GROUP BY v.sku
        ORDER BY venta_bruta DESC NULLS LAST
    """))
    return [dict(r) for r in rows.mappings().all()]


class AgregarSkusRequest(BaseModel):
    skus: List[str]

@router.post("/agregar-skus-productos", dependencies=[Depends(require_rol("admin", "editor"))])
async def agregar_skus_productos(req: AgregarSkusRequest, db: AsyncSession = Depends(get_db)):
    """Crea registros mínimos en productos para SKUs con ventas pero sin catálogo."""
    SIN_MARCA     = 16
    SIN_CATEGORIA = 7
    creados = []
    omitidos = []

    for sku in req.skus:
        # Verificar si ya existe
        existe = await db.execute(text("SELECT 1 FROM productos WHERE sku=:s"), {"s": sku})
        if existe.fetchone():
            omitidos.append(sku)
            continue

        # Tomar datos descriptivos de la última venta con ese SKU
        info = await db.execute(text("""
            SELECT descripcion_producto, marca_erp, categoria_erp
            FROM ventas WHERE sku=:s AND descripcion_producto IS NOT NULL
            ORDER BY fecha DESC LIMIT 1
        """), {"s": sku})
        row = info.mappings().first()
        descripcion = (row["descripcion_producto"] if row else None) or sku

        await db.execute(text("""
            INSERT INTO productos (sku, descripcion, marca_id, categoria_id, precio_venta_bruto, precio_venta_neto)
            VALUES (:sku, :desc, :marca, :cat, 0, 0)
            ON CONFLICT (sku) DO NOTHING
        """), {"sku": sku, "desc": descripcion, "marca": SIN_MARCA, "cat": SIN_CATEGORIA})
        creados.append(sku)

    await db.commit()
    return {"creados": creados, "omitidos": omitidos, "total_creados": len(creados)}


# ── Background sync ────────────────────────────────────────────────────────────

async def _run_sync_background(job_id: str, desde: date, hasta: date, fuente: str, resync: bool = False):
    """Corre el sync ERP en background y actualiza sync_log al terminar."""
    try:
        import httpx
    except ImportError:
        async with AsyncSessionLocal() as db:
            await db.execute(text(
                "UPDATE sync_log SET estado='error', error_msg='httpx no instalado', finished_at=NOW() WHERE job_id=:j"
            ), {"j": job_id})
            await db.commit()
        return

    ERP_URL = os.getenv("ERP_API_URL", "https://dcic-api-production.up.railway.app")
    ERP_KEY = os.getenv("ERP_API_KEY", "")
    ERP_HEADERS = {"X-API-Key": ERP_KEY} if ERP_KEY else {}
    fuentes = ["bsale", "wivo"] if fuente == "all" else [fuente]

    # Siempre borrar el rango antes de insertar — garantía anti-duplicados
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT COUNT(*) FROM ventas WHERE fecha BETWEEN :d AND :h"),
            {"d": desde, "h": hasta}
        )
        n_borrar = result.scalar()
        await db.execute(
            text("DELETE FROM ventas WHERE fecha BETWEEN :d AND :h"),
            {"d": desde, "h": hasta}
        )
        await db.commit()
        log.info(f"[sync_bg {job_id[:8]}] eliminados {n_borrar} registros ({desde} → {hasta}) antes de insertar")

    # Iteracion dia a dia para evitar saltos por paginacion offset inestable
    dias: list[date] = []
    cur = desde
    from datetime import timedelta as _td
    while cur <= hasta:
        dias.append(cur)
        cur += _td(days=1)

    totales = {"insertados": 0, "actualizados": 0, "omitidos": 0,
               "errores_fk": 0, "errores_otros": 0, "sin_sku": 0, "filas_api": 0}
    skus_faltantes: dict[str, dict] = {}
    canales_api:    dict[str, float] = {}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            for ft in fuentes:
                for dia in dias:
                    offset = 0
                    while True:
                        params = {"fecha_desde": str(dia), "fecha_hasta": str(dia),
                                  "fuente": ft, "limit": 100, "offset": offset}
                        try:
                            r = await client.get(f"{ERP_URL}/ventas/", params=params, headers=ERP_HEADERS)
                            r.raise_for_status()
                            data  = r.json()
                            filas = data if isinstance(data, list) else \
                                (data.get("data") or data.get("items") or data.get("ventas") or [])
                        except Exception as e:
                            log.warning(f"[sync_bg {job_id[:8]}] fetch error {ft} {dia}: {e}")
                            break

                        if not filas:
                            break
                        totales["filas_api"] += len(filas)

                        async with AsyncSessionLocal() as db:
                            for idx, row in enumerate(filas):
                                sku   = row.get("sku_id") or row.get("sku") or ""
                                canal = row.get("canal") or ""
                                bruta = float(row.get("venta_bruto") or 0)
                                if canal:
                                    canales_api[canal] = canales_api.get(canal, 0) + bruta

                                if not sku:
                                    totales["sin_sku"] += 1
                                    continue

                                # Solo estado Regular
                                estado = (row.get("estado_orden") or "").strip()
                                if estado != "Regular":
                                    totales["omitidos"] += 1
                                    continue

                                # Solo tipo_linea PRODUCTO
                                tipo_linea = str(row.get("tipo_linea") or "").upper()
                                if tipo_linea != "PRODUCTO":
                                    totales["omitidos"] += 1
                                    continue

                                # Convertir fecha string a date
                                from datetime import date as _date
                                fecha_raw = row.get("fecha")
                                if isinstance(fecha_raw, str):
                                    try:
                                        fecha_val = _date.fromisoformat(fecha_raw[:10])
                                    except Exception:
                                        totales["omitidos"] += 1
                                        continue
                                elif isinstance(fecha_raw, _date):
                                    fecha_val = fecha_raw
                                else:
                                    totales["omitidos"] += 1
                                    continue

                                # Alertar SKUs fuera de catalogo
                                if sku not in skus_faltantes:
                                    async with AsyncSessionLocal() as dbck:
                                        existe_sku = await dbck.execute(
                                            text("SELECT 1 FROM productos WHERE sku=:s"), {"s": sku})
                                        if not existe_sku.fetchone():
                                            skus_faltantes[sku] = {
                                                "sku": sku,
                                                "descripcion": row.get("desc_producto") or "",
                                                "categoria": row.get("categoria_producto") or "",
                                                "marca": row.get("marca_producto") or "",
                                                "canal": canal, "n_ventas": 0, "venta_bruta": 0.0,
                                            }
                                if sku in skus_faltantes:
                                    skus_faltantes[sku]["n_ventas"]    += 1
                                    skus_faltantes[sku]["venta_bruta"] += bruta

                                from decimal import Decimal as _Dec
                                def _dec(v):
                                    try: return _Dec(str(v)) if v is not None else None
                                    except Exception: return None

                                cantidad = int(row.get("cantidad") or 0)
                                id_ext = _id_externo_row(row, offset + idx)
                                n_suborden = row.get("n_pedido")  # campo n_pedido de API = num_suborden en BD

                                try:
                                    await db.execute(text("""
                                        INSERT INTO ventas (
                                            sku, fecha, canal, fuente, estado_orden, estado_despacho,
                                            tipo_linea, cantidad, unidades_devueltas,
                                            precio_total_bruto, valor_unitario_bruto, costo_unitario_clp,
                                            margen_clp, margen_pct,
                                            descripcion_producto, categoria_erp, marca_erp,
                                            id_externo, num_pedido, num_suborden
                                        ) VALUES (
                                            :sku,:fecha,:canal,:fuente,:estado,:despacho,
                                            :tipo,:qty,0,
                                            :precio,:vunit,:costo,
                                            :margen,:margen_pct,
                                            :desc,:cat,:marca,
                                            :ie,:n_orden,:n_pedido
                                        )
                                        ON CONFLICT (id_externo) DO UPDATE SET
                                            sku=EXCLUDED.sku, fecha=EXCLUDED.fecha,
                                            canal=EXCLUDED.canal, fuente=EXCLUDED.fuente,
                                            estado_orden=EXCLUDED.estado_orden,
                                            cantidad=EXCLUDED.cantidad,
                                            precio_total_bruto=EXCLUDED.precio_total_bruto,
                                            valor_unitario_bruto=EXCLUDED.valor_unitario_bruto,
                                            costo_unitario_clp=EXCLUDED.costo_unitario_clp,
                                            margen_clp=EXCLUDED.margen_clp,
                                            margen_pct=EXCLUDED.margen_pct
                                    """), {
                                        "sku": sku, "fecha": fecha_val, "canal": canal,
                                        "fuente": ft, "estado": estado,
                                        "despacho": row.get("estado_despacho"),
                                        "tipo": row.get("tipo_linea"),
                                        "qty": cantidad,
                                        "precio": _dec(row.get("venta_bruto")),
                                        "vunit": _dec(row.get("valor_unitario_bruto")),
                                        "costo": _dec(row.get("costo_unitario_neto")),
                                        "margen": _dec(row.get("margen_clp")),
                                        "margen_pct": _dec(row.get("margen_pct")),
                                        "desc": row.get("desc_producto"),
                                        "cat": row.get("categoria_producto"),
                                        "marca": row.get("marca_producto"),
                                        "ie": id_ext,
                                        "n_orden": row.get("n_orden"),
                                        "n_pedido": n_suborden,
                                    })
                                    totales["insertados"] += 1
                                except Exception as exc:
                                    totales["errores_otros"] += 1
                                    log.warning(f"[sync_bg {job_id[:8]}] insert error {sku}: {exc}")
                                    await db.rollback()
                            await db.commit()

                        offset += len(filas)
                        if len(filas) < 100:
                            break

        import json as _json
        faltantes_list = sorted(skus_faltantes.values(), key=lambda x: -x["venta_bruta"])
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                UPDATE sync_log SET
                    estado='done', finished_at=NOW(),
                    insertados=:ins, actualizados=:upd, omitidos=:omit,
                    errores_fk=:fk, errores_otros=:otros, sin_sku=:sin_sku,
                    meses_procesados=:meses, filas_api=:filas,
                    canales_api=CAST(:canales AS jsonb), skus_faltantes=CAST(:skus AS jsonb)
                WHERE job_id=:j
            """), {
                "ins": totales["insertados"],    "upd":  totales["actualizados"],
                "omit": totales["omitidos"],     "fk":   totales["errores_fk"],
                "otros": totales["errores_otros"],"sin_sku": totales["sin_sku"],
                "meses": len(dias),              "filas": totales["filas_api"],
                "canales": _json.dumps(canales_api),
                "skus":    _json.dumps(faltantes_list),
                "j": job_id,
            })
            await db.commit()
        log.info(f"[sync_bg {job_id[:8]}] done — ins={totales['insertados']} fk={totales['errores_fk']}")

        # Reentrenamiento automático: si hubo inserciones, dispara recálculo de Holt-Winters
        if totales["insertados"] > 0:
            try:
                import subprocess as _sp, sys as _sys, os as _os
                script = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "calcular_metricas.py")
                if _os.path.exists(script):
                    _sp.Popen([_sys.executable, script], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                    log.info(f"[sync_bg {job_id[:8]}] reentrenamiento automático disparado ({totales['insertados']} nuevas ventas)")
            except Exception as re_err:
                log.warning(f"[sync_bg {job_id[:8]}] reentrenamiento automático falló (no crítico): {re_err}")

    except Exception as e:
        log.error(f"[sync_bg {job_id[:8]}] error fatal: {e}", exc_info=True)
        async with AsyncSessionLocal() as db:
            await db.execute(text(
                "UPDATE sync_log SET estado='error', error_msg=:msg, finished_at=NOW() WHERE job_id=:j"
            ), {"msg": str(e)[:500], "j": job_id})
            await db.commit()


@router.post("/sync-erp-start", dependencies=[Depends(require_rol("admin", "editor"))])
async def sync_erp_start(req: SyncErpChunkedRequest, background_tasks: BackgroundTasks,
                         db: AsyncSession = Depends(get_db)):
    """Inicia el sync ERP en segundo plano. Retorna job_id inmediatamente."""
    job_id = str(_uuid.uuid4())
    await db.execute(text("""
        INSERT INTO sync_log (job_id, fuente, desde, hasta, estado)
        VALUES (:j, :f, :d, :h, 'running')
    """), {"j": job_id, "f": req.fuente, "d": req.desde, "h": req.hasta})
    await db.commit()
    background_tasks.add_task(_run_sync_background, job_id, req.desde, req.hasta, req.fuente, req.resync)
    log.info(f"sync-erp-start job={job_id[:8]} desde={req.desde} hasta={req.hasta} fuente={req.fuente}")
    return {"job_id": job_id, "estado": "running", "mensaje": "Sync iniciado en segundo plano"}


@router.get("/sync-status/{job_id}")
async def sync_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Estado actual de un job de sync."""
    row = await db.execute(text("SELECT * FROM sync_log WHERE job_id=:j"), {"j": job_id})
    r = row.mappings().first()
    if not r:
        raise HTTPException(404, "Job no encontrado")
    return dict(r)


@router.get("/sync-log")
async def sync_historial(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    """Historial de sincronizaciones con comparativa de canales por job."""
    rows = await db.execute(text("""
        SELECT job_id, fuente, desde, hasta, estado,
               insertados, actualizados, omitidos, errores_fk, sin_sku,
               meses_procesados, filas_api, canales_api, skus_faltantes,
               started_at, finished_at,
               EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duracion_seg,
               error_msg
        FROM sync_log ORDER BY started_at DESC LIMIT :lim
    """), {"lim": limit})
    return [dict(r) for r in rows.mappings().all()]


class SyncErpRequest(BaseModel):
    desde:   date
    hasta:   date
    fuente:  str = "all"   # "bsale" | "wivo" | "all"
    dry_run: bool = False


@router.post("/sync-erp", dependencies=[Depends(require_api_key)])
async def sync_erp_externo(req: SyncErpRequest):
    """
    Sincroniza ventas desde el ERP externo (Bsale/Wivo) al Forecast DCIC.

    Requiere que FORECAST_API_KEY esté configurada en el entorno del servidor
    (la misma key que usas en el header X-API-Key).

    Nota: Pérgolas, Venta en Verde y Comerc. Dcic Spa ya están disponibles en la API
    y se sincronizan automáticamente. Solo Petwoow, Segunda Seleccion, Dafiti
    y Cta cte Personal aún requieren importación manual desde Excel.
    """
    import asyncio as _asyncio
    import subprocess as _subprocess

    script = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'sync_erp_externo.py'))
    if not os.path.exists(script):
        raise HTTPException(500, "sync_erp_externo.py no encontrado")

    cmd = [
        sys.executable, script,
        '--desde', str(req.desde),
        '--hasta',  str(req.hasta),
        '--fuente', req.fuente,
    ]
    if req.dry_run:
        cmd.append('--dry-run')

    try:
        resultado = await _asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _subprocess.run(
                cmd,
                capture_output=True, text=True,
                cwd=os.path.dirname(script), timeout=300,
            )
        )
        salida = (resultado.stdout or "") + (resultado.stderr or "")
        return {
            "ok":      resultado.returncode == 0,
            "salida":  salida[-4000:],
            "dry_run": req.dry_run,
            "rango":   {"desde": str(req.desde), "hasta": str(req.hasta), "fuente": req.fuente},
        }
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@router.get("/sync-status")
async def sync_status(db: AsyncSession = Depends(get_db)):
    """
    Estado de sincronización: última fecha y total de ventas por fuente.
    Equivale al endpoint R5 descrito en INFORME_API_ADMINISTRADOR.md.
    """
    rows = await db.execute(text("""
        SELECT
            fuente,
            MAX(fecha)      AS ultima_fecha,
            COUNT(*)        AS total_registros,
            SUM(CASE WHEN activo THEN 1 ELSE 0 END) AS activos
        FROM ventas
        GROUP BY fuente
        ORDER BY fuente
    """))
    result = {}
    for r in rows.mappings().all():
        result[r["fuente"] or "sin_fuente"] = {
            "ultima_fecha":     str(r["ultima_fecha"]) if r["ultima_fecha"] else None,
            "total_registros":  int(r["total_registros"]),
            "activos":          int(r["activos"]),
        }
    return result


@router.delete("/{id}", status_code=204)
async def eliminar_venta(id: int, db: AsyncSession = Depends(get_db)):
    v = await db.get(Venta, id)
    if not v:
        raise HTTPException(404, "Venta no encontrada")
    await db.delete(v)
    await db.commit()
