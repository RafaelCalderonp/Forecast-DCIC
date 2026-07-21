"""Constantes globales del sistema Forecast DCIC."""
import os
from decimal import Decimal

# ── IVA Chile (19%) ─────────────────────────────────────────────────────────
# Fuente única para el cálculo precio bruto → neto. Si la tasa cambia,
# se modifica aquí y se propaga a todos los módulos.
IVA_FACTOR      = Decimal("1.19")
IVA_FACTOR_FLOAT = 1.19

# ── Tipo de cambio neutro CLP/USD ────────────────────────────────────────────
# Base de referencia para el ajuste macro en ANCLA-SI-MACRO v2.
# Configurable via variable de entorno USD_NEUTRO (e.g. export USD_NEUTRO=900).
USD_NEUTRO: float = float(os.getenv("USD_NEUTRO", "870.0"))

# ── Umbral de alerta ROJO ────────────────────────────────────────────────────
# SKUs en ROJO cuyo valor de compra supera este monto (CLP) generan alerta.
# Configurable via variable de entorno ALERTA_UMBRAL_CLP.
ALERTA_UMBRAL_CLP: float = float(os.getenv("ALERTA_UMBRAL_CLP", "500000"))

# ── Cap phi — ANCLA-SI-MACRO v2 ─────────────────────────────────────────────
# Límite del ajuste relativo por CAGR dentro del canal (+/- X% sobre PHI_CANAL).
# Configurable via variable de entorno PHI_CAP (e.g. export PHI_CAP=0.05).
PHI_CAP: float = float(os.getenv("PHI_CAP", "0.03"))

# Sensibilidad macro: puntos porcentuales de ajuste phi por cada 10 CLP de
# desviación del tipo de cambio respecto a USD_NEUTRO.
# Configurable via MACRO_SENS (default 0.003 → 0.3% por cada 10 CLP).
MACRO_SENS: float = float(os.getenv("MACRO_SENS", "0.003"))

# ── Parámetros Holt-Winters ──────────────────────────────────────────────────
# Configurables via env: HW_ALPHA, HW_BETA, HW_GAMMA.
# None = optimización automática por statsmodels.
HW_ALPHA = float(os.getenv("HW_ALPHA", "0")) or None   # 0 = auto
HW_BETA  = float(os.getenv("HW_BETA",  "0")) or None
HW_GAMMA = float(os.getenv("HW_GAMMA", "0")) or None
