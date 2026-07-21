"""
AlertService — genera y persiste alertas automáticas del sistema Forecast.
Tipos:
  - MAPE_ALTO:    precisión del modelo > 30%
  - DCI_BAJO:     cobertura < 30 días en productos clase A
  - T90_CYBERDAY: protocolo T-90 antes de CyberDay (activa ~05-Aug-2026)
  - OOS_RIESGO:   forecast_final = 0 con demanda proyectada > 0
"""

from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from forecast.models.forecast_models import AlertaForecast, ForecastResultado


class AlertService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Alertas de precisión MAPE
    # ─────────────────────────────────────────────────────────────────────────

    async def generar_alertas_mape(self, umbral: float = 0.30) -> int:
        """
        Crea alertas MAPE_ALTO para SKUs con mape > umbral y ventas reales.
        Solo períodos pasados (ventas_reales disponibles).
        """
        q = text("""
            SELECT sku, canal, periodo, mape, ventas_reales
            FROM forecast_resultados
            WHERE mape > :umbral
              AND ventas_reales IS NOT NULL
              AND periodo < CURRENT_DATE
            ORDER BY mape DESC
            LIMIT 200
        """)
        result = await self.db.execute(q, {"umbral": umbral})
        rows = result.fetchall()

        n = 0
        for r in rows:
            existe = await self._alerta_existe("MAPE_ALTO", r.sku, r.canal, r.periodo)
            if existe:
                continue
            severidad = "CRITICA" if float(r.mape) > 0.50 else "ALTA" if float(r.mape) > 0.40 else "MEDIA"
            self.db.add(AlertaForecast(
                tipo_alerta="MAPE_ALTO",
                sku=r.sku,
                canal=r.canal,
                periodo=r.periodo,
                valor_actual=float(r.mape),
                umbral=umbral,
                severidad=severidad,
                mensaje=f"MAPE {float(r.mape)*100:.1f}% supera umbral {umbral*100:.0f}% — revisar parámetros HW para {r.sku}/{r.canal}",
            ))
            n += 1

        if n > 0:
            await self.db.commit()
        return n

    # ─────────────────────────────────────────────────────────────────────────
    # Alertas DCI bajo (cobertura)
    # ─────────────────────────────────────────────────────────────────────────

    async def generar_alertas_dci(self, umbral_dias: float = 30.0) -> int:
        """
        Crea alertas DCI_BAJO para SKUs clase A con cobertura < umbral_dias
        en los próximos 3 meses.
        """
        hoy = date.today()
        tres_meses = hoy + timedelta(days=90)

        q = text("""
            SELECT fr.sku, fr.canal, fr.periodo, fr.dci, fr.forecast_final, s.clase_abc
            FROM forecast_resultados fr
            LEFT JOIN (
                SELECT sku, canal, clase_abc
                FROM segmentacion_abc_xyz
                WHERE periodo_inicio = (SELECT MAX(periodo_inicio) FROM segmentacion_abc_xyz)
            ) s ON s.sku = fr.sku AND s.canal = fr.canal
            WHERE fr.dci IS NOT NULL
              AND fr.dci < :umbral
              AND fr.dci > 0
              AND fr.periodo BETWEEN :hoy AND :tres_meses
              AND (s.clase_abc = 'A' OR s.clase_abc IS NULL)
            ORDER BY fr.dci ASC
            LIMIT 100
        """)
        result = await self.db.execute(q, {
            "umbral": umbral_dias,
            "hoy": hoy,
            "tres_meses": tres_meses,
        })
        rows = result.fetchall()

        n = 0
        for r in rows:
            existe = await self._alerta_existe("DCI_BAJO", r.sku, r.canal, r.periodo)
            if existe:
                continue
            dci = float(r.dci)
            severidad = "CRITICA" if dci < 7 else "ALTA" if dci < 15 else "MEDIA"
            self.db.add(AlertaForecast(
                tipo_alerta="DCI_BAJO",
                sku=r.sku,
                canal=r.canal,
                periodo=r.periodo,
                valor_actual=dci,
                umbral=umbral_dias,
                severidad=severidad,
                mensaje=f"DCI {dci:.1f} días — cobertura crítica para {r.sku}/{r.canal} en {str(r.periodo)[:7]}. Forecast: {float(r.forecast_final):.0f} uds.",
            ))
            n += 1

        if n > 0:
            await self.db.commit()
        return n

    # ─────────────────────────────────────────────────────────────────────────
    # Protocolo T-90 CyberDay
    # ─────────────────────────────────────────────────────────────────────────

    async def generar_alertas_t90(self) -> int:
        """
        Activa el protocolo T-90 si estamos a ≤90 días del próximo CyberDay.
        Busca lift factors con nombre 'CyberDay%' y alerta sobre SKUs clase A/B
        que tendrán el lift activo.
        """
        hoy = date.today()

        # Buscar próximo CyberDay en lift_factors
        q_lf = text("""
            SELECT id, nombre_evento, fecha_inicio, multiplicador
            FROM lift_factors
            WHERE nombre_evento ILIKE 'CyberDay%'
              AND fecha_inicio >= :hoy
            ORDER BY fecha_inicio
            LIMIT 1
        """)
        res_lf = await self.db.execute(q_lf, {"hoy": hoy})
        cyber = res_lf.fetchone()

        if not cyber:
            return 0

        dias_restantes = (cyber.fecha_inicio - hoy).days
        if dias_restantes > 90:
            return 0  # todavía fuera de ventana T-90

        # SKUs clase A o B con forecast en el período CyberDay
        q_skus = text("""
            SELECT DISTINCT fr.sku, fr.canal, fr.forecast_final, s.clase_abc
            FROM forecast_resultados fr
            LEFT JOIN (
                SELECT sku, canal, clase_abc
                FROM segmentacion_abc_xyz
                WHERE periodo_inicio = (SELECT MAX(periodo_inicio) FROM segmentacion_abc_xyz)
            ) s ON s.sku = fr.sku AND s.canal = fr.canal
            WHERE fr.periodo = :periodo_cyber
              AND (s.clase_abc IN ('A', 'B') OR s.clase_abc IS NULL)
              AND fr.forecast_final > 0
            ORDER BY fr.forecast_final DESC
            LIMIT 50
        """)
        res_skus = await self.db.execute(q_skus, {
            "periodo_cyber": date(cyber.fecha_inicio.year, cyber.fecha_inicio.month, 1),
        })
        skus = res_skus.fetchall()

        # Una sola alerta global T-90 por evento
        existe_global = await self._alerta_existe("T90_CYBERDAY", "_GLOBAL_", None, cyber.fecha_inicio)
        if not existe_global and dias_restantes <= 90:
            severidad = "CRITICA" if dias_restantes <= 30 else "ALTA" if dias_restantes <= 60 else "MEDIA"
            self.db.add(AlertaForecast(
                tipo_alerta="T90_CYBERDAY",
                sku="_GLOBAL_",
                canal=None,
                periodo=cyber.fecha_inicio,
                valor_actual=float(dias_restantes),
                umbral=90.0,
                severidad=severidad,
                mensaje=f"⚡ PROTOCOLO T-90: {cyber.nombre_evento} en {dias_restantes} días ({cyber.fecha_inicio}). "
                        f"Lift factor ×{float(cyber.multiplicador):.1f} sobre {len(skus)} SKUs activos. "
                        f"Revisar stock, OCs y parámetros HW antes del evento.",
            ))

        n = 1 if not existe_global else 0
        if n > 0:
            await self.db.commit()
        return n

    # ─────────────────────────────────────────────────────────────────────────
    # Alertas OOS (out-of-stock proyectado)
    # ─────────────────────────────────────────────────────────────────────────

    async def generar_alertas_oos(self) -> int:
        """
        Alerta cuando forecast_ajustado > 0 pero forecast_final = 0
        (stock insuficiente para cubrir la demanda proyectada).
        """
        hoy = date.today()
        tres_meses = hoy + timedelta(days=90)

        q = text("""
            SELECT sku, canal, periodo, forecast_ajustado, forecast_final, dci
            FROM forecast_resultados
            WHERE forecast_ajustado > 10
              AND forecast_final = 0
              AND periodo BETWEEN :hoy AND :tres_meses
            LIMIT 100
        """)
        result = await self.db.execute(q, {"hoy": hoy, "tres_meses": tres_meses})
        rows = result.fetchall()

        n = 0
        for r in rows:
            existe = await self._alerta_existe("OOS_RIESGO", r.sku, r.canal, r.periodo)
            if existe:
                continue
            self.db.add(AlertaForecast(
                tipo_alerta="OOS_RIESGO",
                sku=r.sku,
                canal=r.canal,
                periodo=r.periodo,
                valor_actual=0.0,
                umbral=float(r.forecast_ajustado),
                severidad="ALTA",
                mensaje=f"OOS proyectado: demanda {float(r.forecast_ajustado):.0f} uds pero stock = 0 para {r.sku}/{r.canal} en {str(r.periodo)[:7]}",
            ))
            n += 1

        if n > 0:
            await self.db.commit()
        return n

    # ─────────────────────────────────────────────────────────────────────────
    # Ejecutar todas las alertas
    # ─────────────────────────────────────────────────────────────────────────

    async def ejecutar_todas(self) -> dict:
        mape = await self.generar_alertas_mape()
        dci  = await self.generar_alertas_dci()
        t90  = await self.generar_alertas_t90()
        oos  = await self.generar_alertas_oos()
        return {"mape_alto": mape, "dci_bajo": dci, "t90_cyberday": t90, "oos_riesgo": oos, "total": mape + dci + t90 + oos}

    # ─────────────────────────────────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────────────────────────────────

    async def _alerta_existe(self, tipo, sku, canal, periodo) -> bool:
        q = text("""
            SELECT 1 FROM alertas_forecast
            WHERE tipo_alerta = :tipo AND sku = :sku
              AND (canal = :canal OR (canal IS NULL AND :canal IS NULL))
              AND periodo = :periodo
              AND resuelta = FALSE
            LIMIT 1
        """)
        result = await self.db.execute(q, {"tipo": tipo, "sku": sku, "canal": canal, "periodo": periodo})
        return result.fetchone() is not None
