import { useState, useEffect } from "react"
import { getAlertasForecast, resolverAlertaForecast } from "../../services/api"

const API = "/api"

const SEVERIDAD_COLOR = {
  CRITICA: { bg: "#1c0a0a", border: "#7f1d1d", text: "#f87171", badge: "#ef4444" },
  ALTA:    { bg: "#1c1207", border: "#78350f", text: "#fbbf24", badge: "#f59e0b" },
  MEDIA:   { bg: "#0c1a2e", border: "#1e3a5f", text: "#60a5fa", badge: "#3b82f6" },
  BAJA:    { bg: "#0a110c", border: "#14532d", text: "#4ade80", badge: "#22c55e" },
}

const TIPO_ICON = {
  MAPE_ALTO:      "📉",
  DCI_BAJO:       "📦",
  DCI_CRITICO:    "📦",
  T90_CYBERDAY:   "⚡",
  OOS_RIESGO:     "🚫",
  BIAS_ACUMULADO: "⚖️",
  DESVIO_QUINCENAL: "📊",
  FILL_RATE_BAJO: "📋",
}

function fmt(d) { return d ? String(d).slice(0, 10) : "—" }

export default function AlertasForecastPanel() {
  const [data,     setData]     = useState([])
  const [criticas, setCriticas] = useState(0)
  const [loading,  setLoading]  = useState(false)
  const [msg,      setMsg]      = useState(null)
  const [filtros,  setFiltros]  = useState({ tipo: "", severidad: "", sku: "" })
  const [generando, setGenerando] = useState(false)

  useEffect(() => { cargar() }, [filtros]) // eslint-disable-line

  async function cargar() {
    setLoading(true)
    setMsg(null)
    try {
      const params = {}
      if (filtros.tipo)      params.tipo      = filtros.tipo
      if (filtros.severidad) params.severidad = filtros.severidad
      if (filtros.sku)       params.sku       = filtros.sku
      const res = await getAlertasForecast(params)
      setData(res.data || [])
      setCriticas(res.total_criticas || 0)
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  async function resolver(id) {
    try {
      await resolverAlertaForecast(id)
      setData(d => d.filter(a => a.id !== id))
      setCriticas(c => Math.max(0, c - 1))
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    }
  }

  async function generarAlertas() {
    setGenerando(true)
    setMsg(null)
    try {
      const res = await fetch("/api/forecast-dinamico/alertas/generar", { method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem('dcic_token')}` }
      })
      const d = await res.json()
      if (d.ok) {
        setMsg({ tipo: "ok", texto: `Generadas: ${d.mape_alto} MAPE + ${d.dci_bajo} DCI + ${d.t90_cyberday} T90 + ${d.oos_riesgo} OOS = ${d.total} alertas` })
        await cargar()
      }
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setGenerando(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      {/* Header + KPIs */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {criticas > 0 && (
            <div style={{ background: "#1c0a0a", border: "1px solid #7f1d1d", borderRadius: 8, padding: "8px 16px", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 20 }}>🚨</span>
              <div>
                <div style={{ fontSize: 11, color: "#f87171" }}>CRÍTICAS</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: "#ef4444" }}>{criticas}</div>
              </div>
            </div>
          )}
          <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 8, padding: "8px 16px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>ACTIVAS</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#e2e8f0" }}>{data.length}</div>
          </div>
        </div>
        <button onClick={generarAlertas} disabled={generando} style={btnPrimStyle}>
          {generando ? "Ejecutando…" : "🔍 Detectar alertas"}
        </button>
      </div>

      {/* Filtros */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <select value={filtros.tipo} onChange={e => setFiltros(f => ({ ...f, tipo: e.target.value }))} style={selStyle}>
          <option value="">Todos los tipos</option>
          <option value="MAPE_ALTO">📉 MAPE alto</option>
          <option value="DCI_BAJO">📦 DCI bajo</option>
          <option value="DCI_CRITICO">📦 DCI crítico</option>
          <option value="T90_CYBERDAY">⚡ T-90 CyberDay</option>
          <option value="OOS_RIESGO">🚫 OOS riesgo</option>
          <option value="BIAS_ACUMULADO">⚖️ Bias acumulado</option>
        </select>
        <select value={filtros.severidad} onChange={e => setFiltros(f => ({ ...f, severidad: e.target.value }))} style={selStyle}>
          <option value="">Toda severidad</option>
          <option value="CRITICA">🔴 Crítica</option>
          <option value="ALTA">🟠 Alta</option>
          <option value="MEDIA">🔵 Media</option>
          <option value="BAJA">🟢 Baja</option>
        </select>
        <input
          value={filtros.sku}
          onChange={e => setFiltros(f => ({ ...f, sku: e.target.value }))}
          placeholder="Filtrar por SKU…"
          style={{ ...selStyle, width: 180 }}
        />
      </div>

      {msg && (
        <div style={{
          marginBottom: 10, padding: "8px 12px", borderRadius: 6, fontSize: 13,
          background: msg.tipo === "ok" ? "#052e16" : "#1c0a0a",
          color: msg.tipo === "ok" ? "#4ade80" : "#f87171",
          border: `1px solid ${msg.tipo === "ok" ? "#166534" : "#7f1d1d"}`,
        }}>
          {msg.texto}
        </div>
      )}

      {loading ? (
        <div style={{ padding: 32, textAlign: "center", color: "#64748b" }}>Cargando…</div>
      ) : data.length === 0 ? (
        <div style={{ padding: 32, textAlign: "center", color: "#64748b" }}>
          Sin alertas activas. Usa "🔍 Detectar alertas" para ejecutar todos los detectores.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {data.map(a => {
            const sev = SEVERIDAD_COLOR[a.severidad] || SEVERIDAD_COLOR.MEDIA
            return (
              <div key={a.id} style={{
                background: sev.bg, border: `1px solid ${sev.border}`,
                borderRadius: 8, padding: "12px 14px",
                display: "flex", alignItems: "flex-start", gap: 12,
              }}>
                <div style={{ fontSize: 22, flexShrink: 0 }}>{TIPO_ICON[a.tipo_alerta] || "⚠️"}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, background: sev.badge, color: "#000", fontWeight: 700, padding: "1px 8px", borderRadius: 10 }}>
                      {a.severidad}
                    </span>
                    <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{a.tipo_alerta}</span>
                    {a.sku !== "_GLOBAL_" && (
                      <span style={{ fontFamily: "monospace", fontSize: 12, color: sev.text }}>{a.sku}</span>
                    )}
                    {a.canal && <span style={{ fontSize: 12, color: "#64748b" }}>· {a.canal}</span>}
                    <span style={{ fontSize: 11, color: "#64748b" }}>{fmt(a.periodo)}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: sev.text, lineHeight: 1.5 }}>{a.mensaje}</p>
                  <div style={{ marginTop: 4, fontSize: 11, color: "#64748b" }}>
                    Valor: {Number(a.valor_actual).toFixed(2)} · Umbral: {Number(a.umbral).toFixed(2)}
                  </div>
                </div>
                <button
                  onClick={() => resolver(a.id)}
                  style={{ background: "#1e2a3a", color: "#94a3b8", border: "1px solid #2a3a4a", borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}
                >
                  ✓ Resolver
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const selStyle   = { background: "#0d1520", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "5px 10px", fontSize: 13 }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer", whiteSpace: "nowrap" }
