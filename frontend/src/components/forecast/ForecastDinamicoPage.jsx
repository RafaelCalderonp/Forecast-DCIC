import { useState } from "react"
import ForecastDinamicoTabla from "./ForecastDinamicoTabla"
import LiftFactorsPanel from "./LiftFactorsPanel"
import SegmentacionPanel from "./SegmentacionPanel"
import AlertasForecastPanel from "./AlertasForecastPanel"
import OrdenesCompraPanel from "./OrdenesCompraPanel"
import OverridePanel from "./OverridePanel"

const TABS = [
  { id: "dashboard", label: "⚡  Forecast HW"          },
  { id: "lift",      label: "🎯  Lift Factors"          },
  { id: "segmento",  label: "🔷  Segmentación ABC-XYZ"  },
  { id: "alertas",   label: "🔔  Alertas"               },
  { id: "oc",        label: "🛒  Órdenes Compra"        },
  { id: "override",  label: "✏️  Overrides"              },
]

const SUBTITLES = {
  dashboard: "Motor Holt-Winters 3 capas — base + lift + stock",
  lift:      "Ajustes multiplicativos por eventos (CyberDay, temporadas)",
  segmento:  "Clasificación ABC-XYZ por revenue y variabilidad de demanda",
  alertas:   "MAPE alto · DCI crítico · T-90 CyberDay · OOS proyectado",
  oc:        "Sugerencias automáticas de reposición basadas en forecast y stock",
  override:  "Ajuste manual del forecast final por SKU/canal/período",
}

export default function ForecastDinamicoPage() {
  const [tab, setTab] = useState("dashboard")

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Forecast Dinámico</div>
          <div className="page-subtitle">{SUBTITLES[tab]}</div>
        </div>
      </div>

      <div className="tabs" style={{ flexShrink: 0 }}>
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab${tab === t.id ? " active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {tab === "dashboard" && <ForecastDinamicoTabla />}
        {tab === "lift"      && <div style={{ overflowY: "auto", flex: 1 }}><LiftFactorsPanel /></div>}
        {tab === "segmento"  && <div style={{ overflowY: "auto", flex: 1 }}><SegmentacionPanel /></div>}
        {tab === "alertas"   && <div style={{ overflowY: "auto", flex: 1 }}><AlertasForecastPanel /></div>}
        {tab === "oc"        && <div style={{ overflowY: "auto", flex: 1 }}><OrdenesCompraPanel /></div>}
        {tab === "override"  && <div style={{ overflowY: "auto", flex: 1 }}><OverridePanel /></div>}
      </div>
    </div>
  )
}
