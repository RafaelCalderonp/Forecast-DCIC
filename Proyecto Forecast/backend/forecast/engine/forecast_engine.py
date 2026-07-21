"""
Motor de forecast 3 capas para DCIC SpA.
Todas las funciones son puras (sin I/O); los servicios manejan la DB.
Requiere: pandas, numpy, statsmodels
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError:
    ExponentialSmoothing = None  # se instala en requirements.txt


# ── DTOs ──────────────────────────────────────────────────────────────────────

@dataclass
class ForecastResult:
    sku: str
    canal: str
    periodos: list           # list[str] "YYYY-MM-DD" primer día de cada mes
    forecast_base: list      # list[float]
    parametros_hw: dict      # {alpha, beta, gamma, rmse}
    modelo_version: str = "hw_v1"


@dataclass
class ForecastAjustado:
    periodo: str
    forecast_base: float
    lift_aplicado: float
    forecast_ajustado: float
    forecast_final: float
    stock_disponible: Optional[int]
    dci: Optional[float]


# ── 1. Preparar serie temporal ────────────────────────────────────────────────

def preparar_serie_temporal(
    df_ventas: pd.DataFrame,
    sku: str,
    canal: str,
    fecha_inicio: str = "2023-01-01",
    min_periodos: int = 12,
) -> pd.Series:
    """
    Convierte registros de ventas en una Serie mensual con DatetimeIndex frecuencia 'MS'.

    df_ventas requiere columnas: [sku, canal, fecha, cantidad]
    Retorna pd.Series o lanza ValueError si la serie es insuficiente.
    """
    mask = (df_ventas["sku"] == sku) & (df_ventas["canal"] == canal)
    sub = df_ventas.loc[mask].copy()
    sub["fecha"] = pd.to_datetime(sub["fecha"])
    sub = sub[sub["fecha"] >= fecha_inicio]

    if sub.empty:
        raise ValueError(f"Sin datos para {sku}/{canal} desde {fecha_inicio}")

    mensual = (
        sub.set_index("fecha")["cantidad"]
        .resample("MS")
        .sum()
        .fillna(0)
    )

    # Completar rango continuo desde fecha_inicio hasta fin de historia
    idx_completo = pd.date_range(start=fecha_inicio, end=mensual.index.max(), freq="MS")
    mensual = mensual.reindex(idx_completo, fill_value=0)

    if len(mensual) < min_periodos:
        raise ValueError(
            f"Serie {sku}/{canal} tiene {len(mensual)} períodos, mínimo {min_periodos}"
        )

    return mensual


# ── 2. Calibrar Holt-Winters ──────────────────────────────────────────────────

def calibrar_holt_winters(
    serie: pd.Series,
    horizonte_meses: int = 6,
    seasonal_periods: int = 12,
    trend: str = "add",
    seasonal: str = "add",
    damped_trend: bool = True,
    sku: str = "",
    canal: str = "",
) -> ForecastResult:
    """
    Ajusta ExponentialSmoothing y genera forecast para horizonte_meses.
    Si el ajuste falla, usa media histórica como fallback ('fallback_ma').
    """
    if ExponentialSmoothing is None:
        raise ImportError("statsmodels no instalado. Ejecuta: pip install statsmodels")

    periodos_futuros = pd.date_range(
        start=serie.index.max() + pd.DateOffset(months=1),
        periods=horizonte_meses,
        freq="MS",
    )
    periodos_str = [d.strftime("%Y-%m-%d") for d in periodos_futuros]

    try:
        model = ExponentialSmoothing(
            serie,
            trend=trend,
            seasonal=seasonal,
            seasonal_periods=seasonal_periods,
            damped_trend=damped_trend,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True, remove_bias=True)
        predicciones = fit.forecast(horizonte_meses).clip(lower=0).tolist()

        fitted = fit.fittedvalues
        rmse = float(np.sqrt(np.mean((fitted - serie) ** 2)))

        params = {
            "alpha": round(float(fit.params.get("smoothing_level", 0)), 4),
            "beta":  round(float(fit.params.get("smoothing_trend", 0)), 4),
            "gamma": round(float(fit.params.get("smoothing_seasonal", 0)), 4),
            "rmse":  round(rmse, 2),
        }
        version = "hw_v1"

    except Exception:
        # Fallback: media de los últimos 3 meses disponibles
        media = float(serie.iloc[-3:].mean()) if len(serie) >= 3 else float(serie.mean())
        predicciones = [round(max(0.0, media), 2)] * horizonte_meses
        params = {"alpha": 0, "beta": 0, "gamma": 0, "rmse": 0, "fallback": True}
        version = "fallback_ma"

    return ForecastResult(
        sku=sku,
        canal=canal,
        periodos=periodos_str,
        forecast_base=[round(v, 2) for v in predicciones],
        parametros_hw=params,
        modelo_version=version,
    )


# ── 3. Aplicar lift factors ───────────────────────────────────────────────────

def aplicar_lift_factors(
    forecast_base: float,
    sku: str,
    canal: str,
    periodo: str,
    lift_factors: list,
) -> tuple:
    """
    Multiplica forecast_base por los lift_factors activos para sku-canal-periodo.

    lift_factors: lista de dicts con claves
      {canal, sku_pattern, fecha_inicio, fecha_fin, multiplicador}
    Retorna (multiplicador_efectivo: float, forecast_ajustado: float)
    """
    fecha_periodo = pd.to_datetime(periodo).date()
    mult_efectivo = 1.0

    for lf in lift_factors:
        fi = pd.to_datetime(lf["fecha_inicio"]).date()
        ff = pd.to_datetime(lf["fecha_fin"]).date()

        if not (fi <= fecha_periodo <= ff):
            continue

        canal_lf = lf.get("canal")
        if canal_lf and canal_lf != canal:
            continue

        patron = lf.get("sku_pattern")
        if patron and not sku.startswith(patron.rstrip("%")):
            continue

        mult_efectivo *= float(lf["multiplicador"])

    forecast_ajustado = round(forecast_base * mult_efectivo, 2)
    return round(mult_efectivo, 3), forecast_ajustado


# ── 4. Aplicar restricción de stock ──────────────────────────────────────────

def aplicar_restriccion_stock(
    forecast_ajustado: float,
    stock_disponible: Optional[int],
    dias_en_periodo: int = 30,
) -> tuple:
    """
    Limita el forecast al stock disponible y calcula DCI (Días Cobertura Inventario).

    Retorna (forecast_final: float, dci: Optional[float])
    Si stock_disponible es None, retorna (forecast_ajustado, None).
    """
    if stock_disponible is None:
        return forecast_ajustado, None

    demanda_diaria = forecast_ajustado / dias_en_periodo if forecast_ajustado > 0 else 0
    dci = round(stock_disponible / demanda_diaria, 1) if demanda_diaria > 0 else 999.0
    forecast_final = round(min(forecast_ajustado, float(stock_disponible)), 2)

    return forecast_final, dci


# ── 5. Calcular métricas de precisión ────────────────────────────────────────

def calcular_metricas_precision(
    forecast_valores: list,
    ventas_reales: list,
) -> dict:
    """
    Calcula MAPE, Bias y OOS Rate para un SKU-Canal en un rango histórico.

    Retorna dict: {mape, bias, bias_pct, oos_rate, n_periodos}
    """
    if not forecast_valores or not ventas_reales:
        return {"mape": None, "bias": None, "bias_pct": None, "oos_rate": None, "n_periodos": 0}

    f = np.array(forecast_valores, dtype=float)
    r = np.array(ventas_reales, dtype=float)
    n = len(f)

    # MAPE — excluye períodos con ventas reales = 0 (evita división por cero)
    mask_nonzero = r > 0
    if mask_nonzero.sum() > 0:
        mape = float(np.mean(np.abs(f[mask_nonzero] - r[mask_nonzero]) / r[mask_nonzero]))
    else:
        mape = None

    # Bias
    bias = float(np.sum(f - r))
    bias_pct = float(bias / np.sum(r)) if np.sum(r) > 0 else None

    # OOS Rate: períodos donde había demanda real pero forecast_final fue 0
    oos_rate = float(np.sum((r > 0) & (f == 0)) / np.sum(r > 0)) if np.sum(r > 0) > 0 else 0.0

    return {
        "mape":     round(mape, 4) if mape is not None else None,
        "bias":     round(bias, 2),
        "bias_pct": round(bias_pct, 4) if bias_pct is not None else None,
        "oos_rate": round(oos_rate, 4),
        "n_periodos": n,
    }


# ── 6. Segmentación ABC-XYZ ───────────────────────────────────────────────────

def calcular_segmentacion_abc_xyz(
    df_ventas: pd.DataFrame,
    periodo_inicio: str,
    periodo_fin: str,
) -> pd.DataFrame:
    """
    Clasifica todos los SKUs activos en la matriz ABC-XYZ.

    df_ventas requiere columnas: [sku, canal, fecha, cantidad, precio_neto]
    Retorna DataFrame con cols:
      [sku, canal, clase_abc, clase_xyz, coeficiente_variacion,
       revenue_total, unidades_total, pct_revenue_acum]
    """
    df = df_ventas.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    mask = (df["fecha"] >= periodo_inicio) & (df["fecha"] <= periodo_fin)
    df = df.loc[mask]

    if df.empty:
        return pd.DataFrame()

    df["revenue"] = df["cantidad"] * df["precio_neto"].fillna(0)

    # Agrupar revenue total por sku-canal
    agg = (
        df.groupby(["sku", "canal"])
        .agg(revenue_total=("revenue", "sum"), unidades_total=("cantidad", "sum"))
        .reset_index()
    )

    # ABC por revenue acumulado
    agg = agg.sort_values("revenue_total", ascending=False)
    agg["pct_revenue_acum"] = (
        agg["revenue_total"].cumsum() / agg["revenue_total"].sum()
    ).round(4)
    agg["clase_abc"] = "C"
    agg.loc[agg["pct_revenue_acum"] <= 0.70, "clase_abc"] = "A"
    agg.loc[
        (agg["pct_revenue_acum"] > 0.70) & (agg["pct_revenue_acum"] <= 0.90),
        "clase_abc"
    ] = "B"

    # XYZ por coeficiente de variación mensual de unidades
    df["mes"] = df["fecha"].dt.to_period("M")
    mensual = (
        df.groupby(["sku", "canal", "mes"])["cantidad"]
        .sum()
        .reset_index()
    )
    cv_df = (
        mensual.groupby(["sku", "canal"])["cantidad"]
        .agg(["mean", "std"])
        .reset_index()
    )
    cv_df["coeficiente_variacion"] = (cv_df["std"] / cv_df["mean"]).fillna(0).round(4)
    cv_df["clase_xyz"] = "Z"
    cv_df.loc[cv_df["coeficiente_variacion"] < 0.5, "clase_xyz"] = "X"
    cv_df.loc[
        (cv_df["coeficiente_variacion"] >= 0.5) & (cv_df["coeficiente_variacion"] < 1.0),
        "clase_xyz"
    ] = "Y"

    result = agg.merge(
        cv_df[["sku", "canal", "coeficiente_variacion", "clase_xyz"]],
        on=["sku", "canal"],
        how="left",
    )
    result["clase_xyz"] = result["clase_xyz"].fillna("Z")

    return result[["sku", "canal", "clase_abc", "clase_xyz",
                   "coeficiente_variacion", "revenue_total",
                   "unidades_total", "pct_revenue_acum"]]


# ── 7. Generar órdenes de compra sugeridas ────────────────────────────────────

def generar_ordenes_compra_sugeridas(
    df_forecast: pd.DataFrame,
    df_stock: pd.DataFrame,
    lead_time_por_sku: dict,
    stock_seguridad_por_clase: Optional[dict] = None,
    hoy: Optional[date] = None,
) -> pd.DataFrame:
    """
    Genera lista de OC sugeridas basada en forecast_final y stock actual.

    df_forecast: cols [sku, canal, periodo, forecast_final, clase_abc]
    df_stock:    cols [sku, stock_base] (puede incluir bodega_transito)
    lead_time_por_sku: dict {sku: dias_lead_time}
    stock_seguridad_por_clase: dict {'A': 45, 'B': 30, 'C': 15} en días

    Retorna DataFrame con estructura de ordenes_compra_sugeridas.
    """
    if stock_seguridad_por_clase is None:
        stock_seguridad_por_clase = {"A": 45, "B": 30, "C": 15}

    if hoy is None:
        hoy = date.today()

    df_forecast = df_forecast.copy()
    df_forecast["periodo"] = pd.to_datetime(df_forecast["periodo"])

    ocs = []
    for sku, grupo in df_forecast.groupby("sku"):
        lead_time = lead_time_por_sku.get(sku, 30)
        stock_row = df_stock[df_stock["sku"] == sku]
        stock_actual = int(stock_row["stock_base"].iloc[0]) if not stock_row.empty else 0

        clase = grupo["clase_abc"].iloc[0] if "clase_abc" in grupo.columns else "C"
        seg_dias = stock_seguridad_por_clase.get(clase, 15)

        # Ventana de necesidad: desde que llega la OC hasta 30 días después
        fecha_llegada = hoy + timedelta(days=lead_time)
        fecha_necesidad_fin = fecha_llegada + timedelta(days=30)

        demanda_ventana = grupo[
            (grupo["periodo"].dt.date >= fecha_llegada) &
            (grupo["periodo"].dt.date <= fecha_necesidad_fin)
        ]["forecast_final"].sum()

        demanda_diaria = float(grupo["forecast_final"].sum()) / max(len(grupo) * 30, 1)
        stock_minimo = int(demanda_diaria * seg_dias)
        necesidad = demanda_ventana + stock_minimo
        cantidad = max(0, int(necesidad) - stock_actual)

        if cantidad > 0:
            ocs.append({
                "sku":               sku,
                "fecha_sugerida":    hoy.isoformat(),
                "fecha_necesidad":   fecha_llegada.isoformat(),
                "cantidad_sugerida": cantidad,
                "stock_actual":      stock_actual,
                "forecast_demanda":  round(float(demanda_ventana), 2),
                "lead_time_dias":    lead_time,
                "stock_seguridad":   stock_minimo,
                "estado":            "pendiente",
                "clase_abc":         clase,
            })

    return pd.DataFrame(ocs) if ocs else pd.DataFrame()
