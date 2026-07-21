# routers/stock.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
import io, openpyxl
from database import get_db
from models.models import Stock
from schemas.schemas import StockCreate, StockUpdate, StockOut

router = APIRouter()

def _calcular_total(s: Stock) -> int:
    return (s.stock_base + s.stock_full_ml + s.stock_full_fala +
            s.bodega_transito + s.por_arribar + s.pi)

def _to_out(s: Stock) -> StockOut:
    out = StockOut.model_validate(s)
    out.stock_total = _calcular_total(s)
    return out


@router.get("/", response_model=List[StockOut])
async def listar_stock(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).order_by(Stock.sku))
    return [_to_out(s) for s in result.scalars().all()]


@router.get("/{sku}", response_model=StockOut)
async def obtener_stock(sku: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(Stock, sku)
    if not s:
        raise HTTPException(404, f"No hay stock registrado para SKU {sku}")
    return _to_out(s)


@router.post("/", response_model=StockOut, status_code=201)
async def crear_stock(data: StockCreate, db: AsyncSession = Depends(get_db)):
    existente = await db.get(Stock, data.sku)
    if existente:
        raise HTTPException(400, "Ya existe stock para ese SKU. Usa PUT para actualizar.")
    nuevo = Stock(**data.model_dump())
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return _to_out(nuevo)


@router.put("/{sku}", response_model=StockOut)
async def actualizar_stock(sku: str, data: StockUpdate, db: AsyncSession = Depends(get_db)):
    s = await db.get(Stock, sku)
    if not s:
        raise HTTPException(404, f"No hay stock registrado para SKU {sku}")
    for campo, valor in data.model_dump(exclude_none=True).items():
        setattr(s, campo, valor)
    await db.commit()
    await db.refresh(s)
    return _to_out(s)


@router.delete("/{sku}", status_code=204)
async def eliminar_stock(sku: str, db: AsyncSession = Depends(get_db)):
    s = await db.get(Stock, sku)
    if not s:
        raise HTTPException(404, f"No hay stock registrado para SKU {sku}")
    await db.delete(s)
    await db.commit()


class StockBulkItem(BaseModel):
    sku:             str
    stock_base:      int = 0
    stock_jun:       Optional[int] = None
    stock_full_ml:   int = 0
    stock_full_fala: int = 0
    bodega_transito: int = 0
    eta_transito:    Optional[date] = None
    por_arribar:     int = 0
    eta_arribar:     Optional[date] = None
    pi:              int = 0
    eta_pi:          Optional[date] = None


@router.post("/bulk-upsert")
async def bulk_upsert_stock(items: List[StockBulkItem], db: AsyncSession = Depends(get_db)):
    """Inserta o actualiza stock en masa. Solo registra SKUs que existan en productos."""
    if not items:
        return {"upserted": 0}

    skus = [i.sku for i in items]
    result = await db.execute(
        text("SELECT sku FROM productos WHERE sku = ANY(:skus)"),
        {"skus": skus},
    )
    validos = {r[0] for r in result.fetchall()}

    if not validos:
        return {"upserted": 0, "ignorados": len(items)}

    for i in [x for x in items if x.sku in validos]:
        sj = i.stock_jun if i.stock_jun is not None else i.stock_base
        await db.execute(text("""
            INSERT INTO stock (
                sku, stock_base, stock_jun,
                stock_full_ml, stock_full_fala,
                bodega_transito, eta_transito,
                por_arribar, eta_arribar,
                pi, eta_pi,
                fecha_actualizacion
            )
            VALUES (:sku,:base,:sj,:ml,:fala,:trans,:eta_t,:arr,:eta_a,:pi,:eta_p, CURRENT_DATE)
            ON CONFLICT (sku) DO UPDATE SET
                stock_base      = EXCLUDED.stock_base,
                stock_jun       = EXCLUDED.stock_jun,
                stock_full_ml   = EXCLUDED.stock_full_ml,
                stock_full_fala = EXCLUDED.stock_full_fala,
                bodega_transito = EXCLUDED.bodega_transito,
                eta_transito    = COALESCE(EXCLUDED.eta_transito, stock.eta_transito),
                por_arribar     = EXCLUDED.por_arribar,
                eta_arribar     = COALESCE(EXCLUDED.eta_arribar, stock.eta_arribar),
                pi              = EXCLUDED.pi,
                eta_pi          = COALESCE(EXCLUDED.eta_pi, stock.eta_pi),
                fecha_actualizacion = CURRENT_DATE,
                updated_at      = NOW()
        """), {"sku":i.sku,"base":i.stock_base,"sj":sj,"ml":i.stock_full_ml,
               "fala":i.stock_full_fala,"trans":i.bodega_transito,"eta_t":i.eta_transito,
               "arr":i.por_arribar,"eta_a":i.eta_arribar,"pi":i.pi,"eta_p":i.eta_pi})

    await db.commit()
    upserted = sum(1 for i in items if i.sku in validos)
    return {"upserted": upserted, "ignorados": len(items) - upserted}


@router.post("/upload-excel")
async def upload_stock_excel(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Carga stock desde Excel. Columnas esperadas:
    SKU, Stock Base, Full ML, Full Falabella, Bodega Tránsito, ETA Tránsito,
    Por Arribar, ETA Arribar, PI, ETA PI
    """
    from datetime import datetime as dt
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active

        headers = [str(c.value or '').strip().lower() for c in ws[1]]

        def col(nombres):
            for n in nombres:
                for i, h in enumerate(headers):
                    if n in h:
                        return i
            return None

        def parse_fecha(val):
            if not val:
                return None
            if hasattr(val, 'date'):
                return val.date()
            try:
                return dt.strptime(str(val).strip()[:10], '%Y-%m-%d').date()
            except Exception:
                try:
                    return dt.strptime(str(val).strip()[:10], '%d/%m/%Y').date()
                except Exception:
                    return None

        idx_sku       = col(['sku','codigo','código'])
        idx_base      = col(['base','bodega principal','stock base'])
        idx_ml        = col(['full ml','mercado libre','ml'])
        idx_fala      = col(['full fala','falabella','fala'])
        idx_trans     = col(['bodega trans','transito','tránsito','transit'])
        idx_eta_trans = col(['eta trans','eta tráns','eta_trans'])
        idx_arribo    = col(['por arribar','arribo','por llegar'])
        idx_eta_arr   = col(['eta arribar','eta_arr','eta arr'])
        idx_pi        = col([' pi','pi ','pi$','^pi'])
        idx_eta_pi    = col(['eta pi','eta_pi'])

        if idx_sku is None:
            raise HTTPException(400, "Columna SKU/Codigo no encontrada en el Excel")

        items = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            sku = str(row[idx_sku] or '').strip()
            if not sku:
                continue
            def v(i): return int(float(row[i] or 0)) if i is not None and row[i] else 0
            def f(i): return parse_fecha(row[i]) if i is not None else None
            items.append(StockBulkItem(
                sku=sku, stock_base=v(idx_base), stock_full_ml=v(idx_ml),
                stock_full_fala=v(idx_fala),
                bodega_transito=v(idx_trans), eta_transito=f(idx_eta_trans),
                por_arribar=v(idx_arribo),    eta_arribar=f(idx_eta_arr),
                pi=v(idx_pi),                 eta_pi=f(idx_eta_pi),
            ))

        return await bulk_upsert_stock(items, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Error al procesar Excel: {e}")
