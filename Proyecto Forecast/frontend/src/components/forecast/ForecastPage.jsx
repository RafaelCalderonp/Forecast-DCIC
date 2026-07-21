import { useState } from "react"
import AjusteForecastPage from "./AjusteForecastPage"
import CargaForecastExcel from "./CargaForecastExcel"
import TablaForecast from "./TablaForecast"

const TABS = [
  { id: "tabla",  label: "📊  Tabla Forecast"        },
  { id: "ajuste", label: "◎   Ajuste de Proyección"  },
  { id: "carga",  label: "⬆   Carga Excel"           },
]

export default function ForecastPage() {
  const [tab, setTab] = useState("tabla")
  const [reloadKey, setReloadKey] = useState(0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header compartido */}
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <div className="page-title">Forecast 2026</div>
          <div className="page-subtitle">
            {tab === "tabla"  && "Vista pivot editable — haz clic en cualquier celda para editar"}
            {tab === "ajuste" && "Proyección basada en ventas netas de las últimas 6 semanas"}
            {tab === "carga"  && "Carga masiva desde la plantilla Excel oficial"}
          </div>
        </div>
      </div>

      {/* Tabs */}
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

      {/* Contenido */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === "tabla" && <TablaForecast key={reloadKey} />}
        {tab === "ajuste" && (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <AjusteForecastPage sinHeader />
          </div>
        )}
        {tab === "carga" && (
          <div className="page-body" style={{ overflowY: 'auto', flex: 1 }}>
            <div style={{ maxWidth: 900 }}>
              <CargaForecastExcel
                onExito={() => { setReloadKey(k => k + 1); setTab("tabla") }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
