"""
Proyeccion Q4 2026 (Oct-Nov-Dic) — Modelo v2 por Taxonomia de Temporada
========================================================================
Panel de expertos DCIC — Jun-2026

REGLAS POR TIPO DE TEMPORADA:

VERANO / VERANO-ROTATIVO (meses Oct-Dic):
  Comparar siempre temporada contra temporada anterior (no contra H1).
  BASE  = ventas reales Oct-Dic 2025
  PHI   = clip(oct_dic_2025 / oct_dic_2024, 0.85, 1.40)
          Si solo hay 2025 → PHI = 1.0
  qty(m)= BASE * PHI * SI(m) / sum(SI[Oct..Mar])

INVIERNO (Q4 = temporada baja):
  Si SI_promedio(Oct-Dic) < 0.50 × SI_promedio(Abr-Sep) → proyectar 0
  Sino usar ventas residuales históricas Oct-Dic × (1+g)

SIN ESTACIONALIDAD / VERANO-ROTATIVO (meses Abr-Sep):
  BASE  = max(prom_jul_sep_2026 × 3,  ventas_oct_dic_2025_mismo_q)
  qty(m)= BASE_mensual × SI(m) / SI_promedio × (1 + g_anual)

SKUS NUEVOS (sin 2024 ni 2025):
  BASE desde mediana de SKUs proxy (misma categoria, precio +/- 30%)
  SI = 100% categoria.  Flag: HIGH_UNCERTAINTY

SKUS SOLO 2025 (sin 2024):
  Usar total 2025 × 1.25 como proyeccion anual 2026
  SI propio si ≥ 6 meses historico, sino SI categoria

Uso:
  python proyectar_q4_2026.py
"""
import asyncio, asyncpg, os
from statistics import median

DB = dict(host='localhost', port=5432, user='postgres',
          password=os.getenv("PGPASSWORD", "postgres"), database='forecast_dcic')

# Meses de cada temporada
MESES_VERANO   = {10, 11, 12, 1, 2, 3}
MESES_INVIERNO = {4, 5, 6, 7, 8, 9}

# Clip de factor de crecimiento YoY
PHI_MIN, PHI_MAX = 0.85, 1.40
# Credito de crecimiento para SKU nuevo en segundo año
FACTOR_NUEVO_2DO_ANIO = 1.25
# SI_promedio por debajo del cual se considera "fuera de temporada"
UMBRAL_FUERA_TEMPORADA = 0.50


def safe_div(n, d, default=0.0):
    return n / d if d else default


def clip(v, lo, hi):
    return max(lo, min(hi, v))


# ─── Indice estacional ────────────────────────────────────────────────────────

def calcular_si_skus(lista_ventas_por_sku: list[dict]) -> dict:
    """
    Recibe lista de {anio: {mes: qty}} y devuelve SI normalizado a suma=12.
    Pesos: 2024=0.20, 2025=0.35, 2026=0.45
    """
    PESOS = {2024: 0.20, 2025: 0.35, 2026: 0.45}
    si_num: dict[int, float] = {}
    si_den: dict[int, float] = {}
    for v_sku in lista_ventas_por_sku:
        for anio, peso in PESOS.items():
            v_anio = v_sku.get(anio, {})
            if len(v_anio) < 2:
                continue
            total = sum(v_anio.values())
            prom  = total / len(v_anio)
            if prom == 0:
                continue
            for m, q in v_anio.items():
                si_num[m] = si_num.get(m, 0) + (q / prom) * peso
                si_den[m] = si_den.get(m, 0) + peso
    if not si_num:
        return {m: 1.0 for m in range(1, 13)}
    si = {m: safe_div(si_num[m], si_den[m], 1.0) for m in si_num}
    total_si = sum(si.values())
    return {m: v * 12 / total_si for m, v in si.items()} if total_si else {m: 1.0 for m in range(1, 13)}


def si_para_sku(sku: str, ventas: dict, si_cat: dict, min_meses=6) -> dict:
    """SI propio si tiene suficiente historia, sino SI de categoría."""
    v_sku = ventas.get(sku, {})
    n_meses = sum(len(v.keys()) for v in v_sku.values())
    if n_meses >= min_meses:
        return calcular_si_skus([v_sku])
    return si_cat


# ─── Algoritmos por temporada ─────────────────────────────────────────────────

def proyectar_verano(sku: str, ventas: dict, si: dict) -> dict[int, int]:
    """
    VERANO / VERANO-ROTATIVO en Q4 (Oct-Dic).
    Ancla en oct-dic 2025, crece con ratio YoY.
    Distribuye con peso SI dentro de la temporada de verano.
    """
    v = ventas.get(sku, {})
    oct_dic_2025 = sum(v.get(2025, {}).get(m, 0) for m in [10, 11, 12])
    oct_dic_2024 = sum(v.get(2024, {}).get(m, 0) for m in [10, 11, 12])

    if oct_dic_2025 == 0 and oct_dic_2024 == 0:
        return {}  # Sin historia de Q4 → no proyectar aquí (irá a proxy)

    if oct_dic_2025 > 0:
        phi = clip(oct_dic_2025 / oct_dic_2024, PHI_MIN, PHI_MAX) if oct_dic_2024 > 0 else 1.0
        base_q4 = oct_dic_2025 * phi
    else:
        # Solo hay 2024
        base_q4 = oct_dic_2024 * 1.0  # Sin crecimiento si no hay confirmación 2025

    # Distribuir por peso SI dentro de la temporada de verano
    si_temporada = {m: si.get(m, 1.0) for m in MESES_VERANO}
    total_si_temp = sum(si_temporada.values()) or 1.0

    resultado = {}
    for m in [10, 11, 12]:
        qty_raw = base_q4 * si.get(m, 1.0) / total_si_temp
        qty = round(qty_raw)
        if qty > 0:
            resultado[m] = qty
    return resultado


def proyectar_invierno(sku: str, ventas: dict, si: dict) -> dict[int, int]:
    """
    INVIERNO en Q4 (temporada baja).
    Si el SI de Oct-Dic < umbral vs Abr-Sep → proyectar 0.
    Si hay ventas residuales históricas → usarlas.
    """
    si_q4_prom = sum(si.get(m, 0) for m in [10, 11, 12]) / 3
    si_inv_prom = sum(si.get(m, 0) for m in [4, 5, 6, 7, 8, 9]) / 6
    if si_q4_prom < UMBRAL_FUERA_TEMPORADA * si_inv_prom:
        return {10: 0, 11: 0, 12: 0}

    # Ventas residuales históricas Oct-Dic
    v = ventas.get(sku, {})
    resultado = {}
    for m in [10, 11, 12]:
        hist = [v.get(a, {}).get(m, 0) for a in [2024, 2025] if v.get(a, {}).get(m, 0) > 0]
        if hist:
            resultado[m] = round(sum(hist) / len(hist))
    return resultado


def proyectar_sin_estacionalidad(sku: str, ventas: dict, si: dict) -> dict[int, int]:
    """
    SIN ESTACIONALIDAD.
    BASE = max(promedio Jul-Sep 2026 × 3, ventas Oct-Dic 2025)
    Distribuye mes a mes con SI relativo.
    """
    v = ventas.get(sku, {})

    # Velocidad reciente: Jul-Sep 2026 (proxy últimas 8 semanas)
    recientes = [v.get(2026, {}).get(m, 0) for m in [7, 8, 9]]
    prom_reciente = sum(recientes) / 3 if any(r > 0 for r in recientes) else 0
    base_reciente = prom_reciente * 3   # 3 meses = Q4

    # Mismo período año anterior
    oct_dic_2025 = sum(v.get(2025, {}).get(m, 0) for m in [10, 11, 12])
    oct_dic_2024 = sum(v.get(2024, {}).get(m, 0) for m in [10, 11, 12])
    g_anual = clip(safe_div(oct_dic_2025, oct_dic_2024, 1.0) - 1, -0.20, 0.30) if oct_dic_2024 > 0 else 0.0
    base_yoy = oct_dic_2025 * (1 + g_anual) if oct_dic_2025 > 0 else 0

    base_q4 = max(base_reciente, base_yoy)
    if base_q4 == 0:
        return {}

    si_q4 = {m: si.get(m, 1.0) for m in [10, 11, 12]}
    total_si_q4 = sum(si_q4.values()) or 1.0
    resultado = {}
    for m in [10, 11, 12]:
        qty = round(base_q4 * si_q4[m] / total_si_q4)
        if qty > 0:
            resultado[m] = qty
    return resultado


def proyectar_nuevo_solo_2025(sku: str, ventas: dict, si: dict) -> dict[int, int]:
    """SKU incorporado en 2025: usar 2025 × 1.25 como base anual."""
    v2025 = ventas.get(sku, {}).get(2025, {})
    total_2025 = sum(v2025.values())
    if total_2025 == 0:
        return {}
    base_anual = total_2025 * FACTOR_NUEVO_2DO_ANIO
    resultado = {}
    si_total = sum(si.get(m, 1.0) for m in range(1, 13)) or 12
    for m in [10, 11, 12]:
        qty = round(base_anual * si.get(m, 1.0) / si_total)
        if qty > 0:
            resultado[m] = qty
    return resultado


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    conn = await asyncpg.connect(**DB)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS proyeccion_q4_2026 (
            sku        VARCHAR(50) NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
            mes        SMALLINT NOT NULL CHECK (mes IN (10, 11, 12)),
            cantidad   INTEGER NOT NULL DEFAULT 0,
            metodo     VARCHAR(40),
            updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (sku, mes)
        )
    """)
    # Agregar columna metodo si no existe
    await conn.execute("""
        ALTER TABLE proyeccion_q4_2026 ADD COLUMN IF NOT EXISTS metodo VARCHAR(40)
    """)
    await conn.execute("DELETE FROM proyeccion_q4_2026")

    # ── Cargar datos ──────────────────────────────────────────────────────────

    # Ventas por SKU (solo órdenes regulares, activos, no packs)
    rows_v = await conn.fetch("""
        SELECT v.sku,
               EXTRACT(YEAR  FROM v.fecha)::int AS anio,
               EXTRACT(MONTH FROM v.fecha)::int AS mes,
               SUM(v.cantidad - v.unidades_devueltas)::int AS qty
        FROM ventas v
        JOIN productos p ON p.sku = v.sku
        WHERE v.estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM v.fecha) IN (2024, 2025, 2026)
          AND p.activo = TRUE
        GROUP BY v.sku, EXTRACT(YEAR FROM v.fecha), EXTRACT(MONTH FROM v.fecha)
        HAVING SUM(v.cantidad - v.unidades_devueltas) > 0
    """)

    ventas: dict[str, dict] = {}
    for r in rows_v:
        ventas.setdefault(r['sku'], {}).setdefault(r['anio'], {})[r['mes']] = r['qty']

    # Productos activos con temporada
    rows_p = await conn.fetch("""
        SELECT p.sku, COALESCE(t.nombre, '') AS temporada,
               COALESCE(c.nombre, 'Sin categoria') AS categoria,
               COALESCE(p.precio_venta_bruto, 0) AS precio
        FROM productos p
        LEFT JOIN temporadas t ON t.id = p.temporada_id
        LEFT JOIN categorias c ON c.id = p.categoria_id
        WHERE p.activo = TRUE
    """)
    sku_info = {r['sku']: dict(r) for r in rows_p}

    # SI por categoría (usando todos los SKUs de la categoría)
    cat_skus: dict[str, list] = {}
    for sku, info in sku_info.items():
        cat_skus.setdefault(info['categoria'], []).append(sku)

    cat_si_cache: dict[str, dict] = {}
    def get_si_cat(categoria: str) -> dict:
        if categoria not in cat_si_cache:
            skus_cat = cat_skus.get(categoria, [])
            ventas_cat = [ventas.get(s, {}) for s in skus_cat]
            cat_si_cache[categoria] = calcular_si_skus(ventas_cat)
        return cat_si_cache[categoria]

    # SI por SKU (fallback a categoría si historia insuficiente)
    def get_si(sku: str) -> dict:
        cat = sku_info.get(sku, {}).get('categoria', 'Sin categoria')
        return si_para_sku(sku, ventas, get_si_cat(cat))

    # BASE proxy para SKUs sin historia: mediana de SKUs misma categoría y precio +-30%
    def base_proxy_nuevo(sku: str) -> float:
        info = sku_info.get(sku, {})
        precio = float(info.get('precio', 0))
        cat    = info.get('categoria', '')
        candidatos = []
        for s, inf in sku_info.items():
            if s == sku or inf.get('categoria') != cat:
                continue
            p2 = float(inf.get('precio', 0))
            if precio > 0 and p2 > 0 and abs(p2 - precio) / precio > 0.30:
                continue
            v_s = ventas.get(s, {})
            oct_dic_2025 = sum(v_s.get(2025, {}).get(m, 0) for m in [10, 11, 12])
            if oct_dic_2025 > 0:
                candidatos.append(oct_dic_2025)
        return median(candidatos) if candidatos else 0.0

    # ── Proyectar ─────────────────────────────────────────────────────────────

    insertados = 0
    skus_proyectados = set()

    for sku, info in sku_info.items():
        temporada_nombre = info.get('temporada', '').strip()
        v_sku = ventas.get(sku, {})

        tiene_2024 = bool(v_sku.get(2024))
        tiene_2025 = bool(v_sku.get(2025))
        tiene_2026 = bool(v_sku.get(2026))

        si = get_si(sku)

        # Clasificar y proyectar
        es_verano   = 'Verano'  in temporada_nombre and 'Rotativo' not in temporada_nombre
        es_invierno = 'Invierno' in temporada_nombre
        es_rotativo = 'Rotativo' in temporada_nombre
        es_sin_est  = not es_verano and not es_invierno  # incluye Rotativo y Sin Estacionalidad

        resultado  = {}
        metodo     = 'sin_datos'

        if not tiene_2024 and not tiene_2025 and not tiene_2026:
            # Sin historia: proxy
            base = base_proxy_nuevo(sku)
            if base > 0:
                si_total = sum(si.get(m, 1.0) for m in range(1, 13)) or 12
                resultado = {}
                for m in [10, 11, 12]:
                    qty = round(base * si.get(m, 1.0) / si_total)
                    if qty > 0:
                        resultado[m] = qty
                metodo = 'nuevo_proxy_HIGH_UNCERTAINTY'

        elif not tiene_2024 and not tiene_2025 and tiene_2026:
            # Recién incorporado en 2026
            base = base_proxy_nuevo(sku)
            if base > 0:
                si_total = sum(si.get(m, 1.0) for m in range(1, 13)) or 12
                for m in [10, 11, 12]:
                    qty = round(base * si.get(m, 1.0) / si_total)
                    if qty > 0:
                        resultado[m] = qty
                metodo = 'nuevo_2026_proxy_HIGH_UNCERTAINTY'
            else:
                # Usar lo que lleva vendido en 2026 como estimado del año
                total_2026 = sum(v_sku.get(2026, {}).values())
                meses_2026 = len(v_sku.get(2026, {}))
                if meses_2026 > 0:
                    anual_est = total_2026 / meses_2026 * 12
                    si_total = sum(si.get(m, 1.0) for m in range(1, 13)) or 12
                    for m in [10, 11, 12]:
                        qty = round(anual_est * si.get(m, 1.0) / si_total)
                        if qty > 0:
                            resultado[m] = qty
                    metodo = 'nuevo_2026_pace'

        elif not tiene_2024 and tiene_2025:
            # Incorporado en 2025 → solo 1 año de historia
            resultado = proyectar_nuevo_solo_2025(sku, ventas, si)
            metodo = 'nuevo_2025_factor125'

        else:
            # Historia normal (tiene 2024 y/o 2025)
            if es_verano or (es_rotativo and True):  # Q4 siempre es temporada verano
                resultado = proyectar_verano(sku, ventas, si)
                metodo = 'verano_yoy'
                if not resultado:
                    # Fallback: sin historia Q4 → usar SI total
                    resultado = proyectar_sin_estacionalidad(sku, ventas, si)
                    metodo = 'verano_fallback_sin_est'

            elif es_invierno:
                resultado = proyectar_invierno(sku, ventas, si)
                metodo = 'invierno_residual'

            else:
                # Sin estacionalidad
                resultado = proyectar_sin_estacionalidad(sku, ventas, si)
                metodo = 'sin_estacionalidad_8sem'

        # Insertar en DB
        for mes, qty in resultado.items():
            if qty > 0:
                await conn.execute("""
                    INSERT INTO proyeccion_q4_2026 (sku, mes, cantidad, metodo)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (sku, mes) DO UPDATE
                    SET cantidad=$3, metodo=$4, updated_at=NOW()
                """, sku, mes, qty, metodo)
                insertados += 1
                skus_proyectados.add(sku)

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  PROYECCION Q4 2026 — Modelo v2 por Taxonomia")
    print(f"{'='*60}")
    for mes in [10, 11, 12]:
        s = await conn.fetchval("SELECT SUM(cantidad) FROM proyeccion_q4_2026 WHERE mes=$1", mes)
        n = {10: 'Oct', 11: 'Nov', 12: 'Dic'}[mes]
        print(f"  {n}-2026: {s or 0:>10,} uds")

    print(f"\n  SKUs proyectados: {len(skus_proyectados)}")
    print(f"  Filas insertadas: {insertados}")

    # Desglose por método
    rows_m = await conn.fetch("""
        SELECT metodo, COUNT(DISTINCT sku) AS n_skus, SUM(cantidad) AS total
        FROM proyeccion_q4_2026 GROUP BY metodo ORDER BY total DESC
    """)
    print(f"\n  {'Método':<40} {'SKUs':>6} {'Unidades':>10}")
    print(f"  {'-'*58}")
    for r in rows_m:
        print(f"  {(r['metodo'] or '?'):<40} {r['n_skus']:>6} {r['total']:>10,}")

    # Verificación R6683
    r6683 = await conn.fetch("SELECT mes, cantidad, metodo FROM proyeccion_q4_2026 WHERE sku='R6683' ORDER BY mes")
    if r6683:
        print(f"\n  R6683 (verificacion):")
        for r in r6683:
            print(f"    Mes {r['mes']}: {r['cantidad']} uds  [{r['metodo']}]")
    print()

    await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
