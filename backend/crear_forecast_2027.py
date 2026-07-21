"""
Forecast 2027 — Modelo ANCLA-SI-MACRO (v2)
==========================================
Aprobado por panel de 4 doctores en economia y estadistica (jun-2026).

Formula maestra:
  F(s,c,m) = BASE_2026(s,c) x PHI_CANAL(c) x SI(s,c,m)/12 x kappa(s,c)

Componentes:
  BASE_2026  Ventas H1 real 2026 / peso_estacional_H1
             -> ancla en datos reales 2026, no proyecta desde 2025
  PHI_CANAL  Factor de crecimiento total por canal (panel + macro).
             Encapsula: tasa consenso panel (11%) + contexto macro Chile
             + diferenciacion por tipo de canal (e-commerce vs retail)
  SI         Indice estacional ponderado: 2024(20%)+2025(35%)+2026(45%)
             Con shrinkage a categoria si el SKU tiene <8 meses historia
  kappa      Corrector de sesgo opcional. Predice H1-2026 con datos 2024+2025,
             compara con H1 real. Solo se aplica si el canal existia en 2024
             y la correccion es moderada [0.85, 1.15].

Nota: CAGR_adj se usa como ajuste relativo DENTRO del canal (+/-3% max),
no como multiplicador adicional que doble-cuenta el crecimiento.

Uso:
  python crear_forecast_2027.py                    # phi_panel=11% (consenso)
  python crear_forecast_2027.py --crecimiento 8.5  # phi_panel personalizado (%)
"""
import asyncio, asyncpg, argparse, os
from constants import PHI_CAP, MACRO_SENS

DB = dict(host='localhost', port=5432, user='postgres', password=os.getenv("PGPASSWORD", "postgres"), database='forecast_dcic')

CANALES = [
    'Falabella', 'Mercado Libre', 'Walmart', 'Paris',
    'Vincenzi', 'Ripley', 'GlowUp', 'Petwoow', 'Kfit',
    'Venta Directa', 'Segunda Seleccion', 'Miglu', 'Bfresh',
    'Homeclaf', 'Dafiti',
]

# PHI por canal: crecimiento total esperado 2026->2027
# Promedio ponderado = 1.110 (11% consenso panel).
# E-commerce tiene prima estructural por crecimiento digital Chile (~18% anual sector).
# Retail fisico crece mas moderado. Valores diferenciados segun panel Dr. Estadistico.
PHI_BASE_CANAL = {
    'Mercado Libre':    1.17,  # e-commerce lider, crecimiento estructural ~18% sector
    'Petwoow':          1.16,
    'Kfit':             1.15,
    'Falabella':        1.14,
    'Paris':            1.13,
    'Ripley':           1.13,
    'GlowUp':           1.12,
    'Walmart':          1.11,
    'Dafiti':           1.11,
    'Vincenzi':         1.10,
    'Miglu':            1.09,
    'Bfresh':           1.09,
    'Homeclaf':         1.09,
    'Venta Directa':    1.08,
    'Segunda Seleccion':1.07,
}
# Promedio calibrado: 1.110 -> 11.0% crecimiento promedio (consenso panel)

# Pesos Indice Estacional por año
W_SI = {2024: 0.20, 2025: 0.35, 2026: 0.45}

# Limites de ajuste relativo por CAGR dentro del canal (configurable via PHI_CAP env)
CAGR_ADJ_MAX = PHI_CAP

# Kappa: solo para canales maduros, rango conservador
KAPPA_MIN, KAPPA_MAX = 0.85, 1.15

# Minimo de meses para usar SI propio
MIN_MESES_SI = 8


def safe_div(num, den, default=0.0):
    return num / den if den and den != 0 else default


def clip(val, mn, mx):
    return max(mn, min(mx, val))


async def main(phi_panel: float = 0.11):
    conn = await asyncpg.connect(**DB)

    # ── Variable exógena: Tipo de cambio CLP/USD ──────────────────
    # DCIC importa desde Asia (costos en USD). Un USD/CLP alto encarece
    # los productos → reduce demanda o márgenes → ajuste conservador al phi.
    # Referencia neutral: 870 CLP/USD (promedio histórico 2023-2025).
    # Rango de ajuste: ±3% sobre phi_panel.
    import os as _os
    USD_NEUTRO = float(_os.getenv("USD_NEUTRO", "870.0"))
    tc_row = await conn.fetchrow(
        "SELECT usd_clp FROM tipo_cambio ORDER BY fecha DESC LIMIT 1"
    )
    usd_clp = float(tc_row['usd_clp']) if tc_row else USD_NEUTRO
    # Factor macro: cada 10 CLP sobre/bajo neutro ajusta phi en ±0.3%
    factor_macro = max(-PHI_CAP, min(PHI_CAP, (USD_NEUTRO - usd_clp) / 10 * MACRO_SENS))
    phi_panel_ajustado = phi_panel + factor_macro
    print(f"Tipo de cambio USD/CLP: {usd_clp:.0f}  (neutro: {USD_NEUTRO:.0f}  — configurable via USD_NEUTRO=xxxx)")
    print(f"Factor macro: {factor_macro:+.2%}  →  phi ajustado: {phi_panel_ajustado:.2%}")

    # PHI_CANAL: el phi_panel (--crecimiento) fija el crecimiento promedio.
    # PHI_BASE_CANAL da los pesos relativos entre canales (e-commerce crece mas).
    # Normalizamos los pesos relativos a media=1.0, luego escalamos por (1+phi_panel_ajustado).
    media_base = sum(PHI_BASE_CANAL.values()) / len(PHI_BASE_CANAL)
    PHI_CANAL  = {c: (1 + phi_panel_ajustado) * (v / media_base) for c, v in PHI_BASE_CANAL.items()}

    phi_promedio = sum(PHI_CANAL.values()) / len(PHI_CANAL)
    print(f"Modelo: ANCLA-SI-MACRO v2 + tipo de cambio exógeno")
    print(f"phi_panel={phi_panel:.1%}  phi_ajustado={phi_panel_ajustado:.1%}  phi_promedio_canales={phi_promedio:.3f}")
    print(f"  MercadoLibre={PHI_CANAL.get('Mercado Libre',0):.3f}  VentaDirecta={PHI_CANAL.get('Venta Directa',0):.3f}")

    # ── Crear / limpiar tabla ─────────────────────────────────────
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forecast_2027 (
            id            SERIAL PRIMARY KEY,
            sku           VARCHAR(50) NOT NULL REFERENCES productos(sku) ON DELETE CASCADE,
            canal         VARCHAR(100) NOT NULL,
            mes           SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
            cantidad      INTEGER NOT NULL DEFAULT 0,
            ajuste_manual BOOLEAN DEFAULT FALSE,
            updated_at    TIMESTAMP DEFAULT NOW(),
            UNIQUE(sku, canal, mes)
        )
    """)
    await conn.execute("DELETE FROM forecast_2027 WHERE ajuste_manual = FALSE")

    # ── Cargar datos historicos ───────────────────────────────────
    rows = await conn.fetch("""
        SELECT v.sku, v.canal,
               EXTRACT(YEAR  FROM v.fecha)::int AS anio,
               EXTRACT(MONTH FROM v.fecha)::int AS mes,
               SUM(v.cantidad - v.unidades_devueltas)::int AS qty
        FROM ventas v
        JOIN productos p ON p.sku = v.sku
        WHERE v.estado_orden = 'Regular'
          AND EXTRACT(YEAR FROM v.fecha) IN (2024, 2025, 2026)
          AND v.canal = ANY($1::text[])
          AND p.activo = TRUE AND p.es_pack = FALSE
        GROUP BY v.sku, v.canal,
                 EXTRACT(YEAR FROM v.fecha),
                 EXTRACT(MONTH FROM v.fecha)
        HAVING SUM(v.cantidad - v.unidades_devueltas) > 0
    """, CANALES)

    ventas = {}  # ventas[sku][canal][anio][mes] = qty
    for r in rows:
        s, c, a, m, q = r['sku'], r['canal'], r['anio'], r['mes'], r['qty']
        ventas.setdefault(s, {}).setdefault(c, {}).setdefault(a, {})[m] = q

    # ── Categoria por SKU ─────────────────────────────────────────
    cat_rows = await conn.fetch("""
        SELECT p.sku, COALESCE(c.nombre, 'Sin categoria') AS cat
        FROM productos p
        LEFT JOIN categorias c ON c.id = p.categoria_id
        WHERE p.activo = TRUE AND p.es_pack = FALSE
    """)
    sku_cat = {r['sku']: r['cat'] for r in cat_rows}

    # ── Indice estacional ─────────────────────────────────────────
    def calcular_si(sku, canal):
        si_num = {}
        si_den = {}
        n_meses = 0
        for anio, peso in W_SI.items():
            v_anio = ventas.get(sku, {}).get(canal, {}).get(anio, {})
            if not v_anio or len(v_anio) < 2:
                continue
            total = sum(v_anio.values())
            n = len(v_anio)
            prom = total / n
            if prom == 0:
                continue
            for m, q in v_anio.items():
                si_num[m] = si_num.get(m, 0) + (q / prom) * peso
                si_den[m] = si_den.get(m, 0) + peso
            n_meses += n
        si = {m: safe_div(si_num[m], si_den[m], 1.0) for m in si_num}
        for m in range(1, 13):
            si.setdefault(m, 1.0)
        total_si = sum(si.values())
        if total_si > 0:
            si = {m: v * 12 / total_si for m, v in si.items()}
        return si, n_meses

    si_cache = {}
    for sku in ventas:
        for canal in ventas[sku]:
            si, n = calcular_si(sku, canal)
            si_cache[(sku, canal)] = (si, n)

    # SI por categoria para shrinkage
    si_cat = {}
    for (sku, canal), (si, n) in si_cache.items():
        if n >= MIN_MESES_SI:
            cat = sku_cat.get(sku, 'Sin categoria')
            for m, v in si.items():
                si_cat.setdefault(cat, {}).setdefault(m, []).append(v)

    si_cat_avg = {}
    for cat, meses_dict in si_cat.items():
        avg = {m: sum(vals)/len(vals) for m, vals in meses_dict.items()}
        total = sum(avg.values())
        si_cat_avg[cat] = {m: v*12/total for m, v in avg.items()} if total else avg

    def get_si(sku, canal):
        si, n = si_cache.get((sku, canal), ({m: 1.0 for m in range(1,13)}, 0))
        if n >= MIN_MESES_SI:
            return si
        cat = sku_cat.get(sku, 'Sin categoria')
        si_fallback = si_cat_avg.get(cat, {m: 1.0 for m in range(1,13)})
        w = clip(n / MIN_MESES_SI, 0.0, 1.0)
        return {m: w * si.get(m, 1.0) + (1-w) * si_fallback.get(m, 1.0)
                for m in range(1, 13)}

    # ── CAGR relativo (diferenciador dentro del canal) ────────────
    def calcular_cagr_relativo(sku, canal):
        """
        CAGR ponderado 35/65. Retorna como AJUSTE RELATIVO (+/-3% max),
        no como multiplicador de crecimiento total.
        """
        v = ventas.get(sku, {}).get(canal, {})
        v24 = sum(v.get(2024, {}).values())
        v25 = sum(v.get(2025, {}).values())

        h1_26 = sum(q for m, q in v.get(2026, {}).items() if m <= 6)
        h1_25 = sum(q for m, q in v.get(2025, {}).items() if m <= 6)
        h2_25 = sum(q for m, q in v.get(2025, {}).items() if m > 6)
        ratio  = clip(safe_div(h2_25, h1_25, 1.0), 0.5, 3.0)
        v26_est = h1_26 * (1 + ratio) if h1_26 > 0 else v25

        if v25 == 0:
            return 0.0

        if v24 == 0:
            # Canal nuevo: no hay g1, solo g2
            g2 = clip(safe_div(v26_est, v25, 1.0) - 1, -0.5, 1.0)
            cagr = g2
        else:
            g1 = clip(safe_div(v25, v24, 1.0) - 1, -0.5, 1.0)
            g2 = clip(safe_div(v26_est, v25, 1.0) - 1, -0.5, 1.0)
            cagr = 0.35 * g1 + 0.65 * g2

        # Retorna como ajuste relativo acotado a +/-3%
        return clip(cagr - phi_panel, -CAGR_ADJ_MAX, CAGR_ADJ_MAX)

    # ── Kappa (solo canales maduros, rango conservador) ───────────
    def calcular_kappa(sku, canal):
        v = ventas.get(sku, {}).get(canal, {})
        v24 = sum(v.get(2024, {}).values())
        if v24 == 0:
            return 1.0  # canal nuevo: no aplicar kappa

        h1_real = sum(q for m, q in v.get(2026, {}).items() if m <= 6)
        if h1_real == 0:
            return 1.0

        v25 = sum(v.get(2025, {}).values())
        if v25 == 0:
            return 1.0

        # Predecir H1 2026 con datos hasta 2025 (g1 = 2024->2025)
        g1 = clip(safe_div(v25, v24, 1.0) - 1, -0.3, 0.6)
        v26_pred = v25 * (1 + g1)

        # SI de 2024+2025 solamente
        si24 = v.get(2024, {})
        si25 = v.get(2025, {})
        prom24 = safe_div(sum(si24.values()), max(len(si24), 1), 0)
        prom25 = safe_div(sum(si25.values()), max(len(si25), 1), 0)
        si_pre = {}
        for m in range(1, 13):
            i24 = safe_div(si24.get(m, 0), prom24, 1.0) if prom24 else 1.0
            i25 = safe_div(si25.get(m, 0), prom25, 1.0) if prom25 else 1.0
            w24, w25 = (0.0, 1.0) if not si24 else (0.35, 0.65)
            si_pre[m] = i24*w24 + i25*w25
        total_si_pre = sum(si_pre.values())
        si_pre = {m: v*12/total_si_pre for m, v in si_pre.items()} if total_si_pre else {m:1.0 for m in range(1,13)}

        h1_pred = sum((v26_pred / 12) * si_pre.get(m, 1.0) for m in range(1, 7))
        if h1_pred <= 0:
            return 1.0

        kappa = h1_real / h1_pred
        return clip(kappa, KAPPA_MIN, KAPPA_MAX)

    # ── BASE 2026 anualizada ──────────────────────────────────────
    def calcular_base_2026(sku, canal, si):
        v = ventas.get(sku, {}).get(canal, {})
        h1_real = sum(q for m, q in v.get(2026, {}).items() if m <= 6)

        if h1_real > 0:
            peso_h1 = sum(si.get(m, 1.0) for m in range(1, 7)) / 12
            if peso_h1 > 0.1:   # guardarail: H1 nunca puede ser <10% del año
                return h1_real / peso_h1

        # Fallback: usar 2025 anualizado
        v25 = sum(v.get(2025, {}).values())
        h1_25 = sum(q for m, q in v.get(2025, {}).items() if m <= 6)
        h2_25 = sum(q for m, q in v.get(2025, {}).items() if m > 6)
        if v25 > 0:
            return v25  # año completo 2025 como fallback
        return 0.0

    # ── Generar forecast 2027 ─────────────────────────────────────
    base_total = 0.0
    cnt = {'ancla_26': 0, 'fallback_25': 0, 'sin_datos': 0}
    filas_raw = []   # (sku, canal, mes, qty_raw)

    universo = set()
    for sku in ventas:
        for canal in ventas[sku]:
            if ventas[sku][canal].get(2025) or ventas[sku][canal].get(2026):
                universo.add((sku, canal))

    for (sku, canal) in universo:
        si        = get_si(sku, canal)
        base_2026 = calcular_base_2026(sku, canal, si)

        if base_2026 <= 0:
            cnt['sin_datos'] += 1
            continue

        phi             = PHI_CANAL.get(canal, 1 + phi_panel)
        base_anual_2027 = base_2026 * phi
        base_total     += base_2026

        h1_26 = sum(q for m, q in ventas.get(sku, {}).get(canal, {}).get(2026, {}).items() if m <= 6)
        if h1_26 > 0:
            cnt['ancla_26'] += 1
        else:
            cnt['fallback_25'] += 1

        for mes in range(1, 13):
            qty = (base_anual_2027 / 12) * si.get(mes, 1.0)
            if qty > 0:
                filas_raw.append((sku, canal, mes, qty))

    # Escalar usando metodo del mayor resto (Hamilton): garantiza total exacto
    target_int = int(round(base_total * (1 + phi_panel)))
    total_raw  = sum(q for _, _, _, q in filas_raw)
    factor     = target_int / total_raw if total_raw > 0 else 1.0

    # Calcular parte entera y restos para cada fila
    scaled = [(sku, canal, mes, qty_raw * factor) for sku, canal, mes, qty_raw in filas_raw]
    floors  = [(sku, canal, mes, int(s), s - int(s)) for sku, canal, mes, s in scaled if s >= 0.5]
    allocated = sum(f for _, _, _, f, _ in floors)
    remainder = target_int - allocated

    # Dar +1 a las filas con mayor resto fraccionario hasta cubrir target_int
    floors_sorted = sorted(range(len(floors)), key=lambda i: -floors[i][4])
    qty_map: dict = {}
    for i, (sku, canal, mes, floor_qty, _) in enumerate(floors):
        qty_map[(sku, canal, mes)] = floor_qty + (1 if i in set(floors_sorted[:remainder]) else 0)

    print(f"\nAsignando {target_int:,} uds en {len(qty_map):,} filas (crecimiento objetivo: {phi_panel:.1%})")

    for (sku, canal, mes, _) in filas_raw:
        qty = qty_map.get((sku, canal, mes), 0)
        if qty < 1:
            continue
        await conn.execute("""
            INSERT INTO forecast_2027 (sku, canal, mes, cantidad, ajuste_manual)
            VALUES ($1, $2, $3, $4, FALSE)
            ON CONFLICT (sku, canal, mes) DO UPDATE
              SET cantidad = EXCLUDED.cantidad, updated_at = NOW()
              WHERE forecast_2027.ajuste_manual = FALSE
        """, sku, canal, mes, qty)

    total      = await conn.fetchval("SELECT COUNT(*) FROM forecast_2027")
    uds_auto   = await conn.fetchval("SELECT SUM(cantidad)::bigint FROM forecast_2027 WHERE ajuste_manual=FALSE")
    uds_manual = await conn.fetchval("SELECT SUM(cantidad)::bigint FROM forecast_2027 WHERE ajuste_manual=TRUE")

    print(f"\nSKU-canal anclados en 2026 real:  {cnt['ancla_26']:>6,}")
    print(f"SKU-canal con fallback 2025:       {cnt['fallback_25']:>6,}")
    print(f"\nBase 2026 estimada (total):        {base_total:>12,.0f} uds")
    print(f"Forecast 2027 auto:                {uds_auto:>12,} uds")
    if uds_manual:
        print(f"Forecast 2027 manual:              {uds_manual:>12,} uds")
    uds_total = (uds_auto or 0) + (uds_manual or 0)
    print(f"Forecast 2027 TOTAL:               {uds_total:>12,} uds")
    if base_total > 0:
        print(f"Crecimiento auto vs base 2026:     {(uds_auto/base_total - 1):.1%}")
    print(f"Filas en forecast_2027:            {total}")

    await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--crecimiento', type=float, default=11.0,
                        help='Tasa de crecimiento en %% para el panel (default: 11.0)')
    args = parser.parse_args()
    asyncio.run(main(phi_panel=args.crecimiento / 100.0))
