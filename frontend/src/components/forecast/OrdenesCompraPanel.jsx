import { useState, useEffect } from "react"
import { getOrdenesSugeridas } from "../../services/api"

const API = "/api"
const authHdr = () => ({ Authorization: `Bearer ${localStorage.getItem('dcic_token')}` })

function fmt(n) { return n != null ? Number(n).toLocaleString("es-CL") : "—" }
function fmtDate(d) { return d ? String(d).slice(0, 10) : "—" }

const ESTADO_COLOR = {
  pendiente: { bg: "#0c1a2e", border: "#1e3a5f", text: "#60a5fa" },
  aprobada:  { bg: "#052e16", border: "#166534", text: "#4ade80" },
  rechazada: { bg: "#1c0a0a", border: "#7f1d1d", text: "#f87171" },
  emitida:   { bg: "#1c1207", border: "#78350f", text: "#fbbf24" },
}

const ABC_COLOR = { A: "#22c55e", B: "#f59e0b", C: "#94a3b8" }

export default function OrdenesCompraPanel() {
  const [ocs,      setOcs]      = useState([])
  const [loading,  setLoading]  = useState(false)
  const [msg,      setMsg]      = useState(null)
  const [filtro,   setFiltro]   = useState({ estado: "pendiente", clase_abc: "" })
  const [generando, setGenerando] = useState(false)
  const [horizonte, setHorizonte] = useState(90)

  useEffect(() => { cargar() }, [filtro]) // eslint-disable-line

  async function cargar() {
    setLoading(true)
    setMsg(null)
    try {
      const params = {}
      if (filtro.estado)    params.estado    = filtro.estado
      if (filtro.clase_abc) params.clase_abc = filtro.clase_abc
      const data = await getOrdenesSugeridas(params)
      setOcs(data || [])
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  async function generar() {
    if (!window.confirm(`¿Generar OC sugeridas para los próximos ${horizonte} días? Se eliminarán las pendientes actuales.`)) return
    setGenerando(true)
    setMsg(null)
    try {
      const res = await fetch(`/api/forecast-dinamico/ordenes-compra/generar?horizonte_dias=${horizonte}`, {
        method: "POST", headers: authHdr(),
      })
      const d = await res.json()
      if (d.ok) {
        setMsg({ tipo: "ok", texto: `${d.ordenes_generadas} órdenes generadas. ${d.msg || ""}` })
        await cargar()
      } else {
        setMsg({ tipo: "error", texto: d.detail || "Error" })
      }
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setGenerando(false)
    }
  }

  async function cambiarEstado(id, estado) {
    try {
      await fetch(`/api/forecast-dinamico/ordenes-compra/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHdr() },
        body: JSON.stringify({ estado }),
      })
      setOcs(prev => prev.map(oc => oc.id === id ? { ...oc, estado } : oc))
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    }
  }

  const totalUds = ocs.filter(o => o.estado === "pendiente").reduce((s, o) => s + (o.cantidad_sugerida || 0), 0)

  return (
    <div style={{ padding: 16 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <select value={filtro.estado} onChange={e => setFiltro(f => ({ ...f, estado: e.target.value }))} style={selStyle}>
          <option value="">Todos los estados</option>
          <option value="pendiente">Pendientes</option>
          <option value="aprobada">Aprobadas</option>
          <option value="rechazada">Rechazadas</option>
          <option value="emitida">Emitidas</option>
        </select>
        <select value={filtro.clase_abc} onChange={e => setFiltro(f => ({ ...f, clase_abc: e.target.value }))} style={selStyle}>
          <option value="">ABC: todos</option>
          <option value="A">Solo A</option>
          <option value="B">Solo B</option>
          <option value="C">Solo C</option>
        </select>

        <span style={{ flex: 1 }} />

        <label style={{ fontSize: 12, color: "#64748b" }}>Horizonte:</label>
        <select value={horizonte} onChange={e => setHorizonte(Number(e.target.value))} style={{ ...selStyle, width: 120 }}>
          <option value={30}>30 días</option>
          <option value={60}>60 días</option>
          <option value={90}>90 días</option>
          <option value={120}>120 días</option>
        </select>
        <button onClick={generar} disabled={generando} style={btnPrimStyle}>
          {generando ? "Calculando…" : "🛒 Generar OCs"}
        </button>
      </div>

      {/* KPIs */}
      {ocs.length > 0 && (
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <Kpi label="OCs pendientes" value={ocs.filter(o => o.estado === "pendiente").length} />
          <Kpi label="Unidades totales" value={fmt(totalUds)} />
          <Kpi label="SKUs afectados" value={new Set(ocs.map(o => o.sku)).size} />
        </div>
      )}

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
      ) : ocs.length === 0 ? (
        <div style={{ padding: 32, textAlign: "center", color: "#64748b" }}>
          Sin órdenes de compra. Usa "🛒 Generar OCs" para calcular las necesidades de reposición.
          <br /><span style={{ fontSize: 12, marginTop: 8, display: "block" }}>Requiere forecast calculado previamente (⚡ Forecast HW).</span>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#0d1520" }}>
                {["SKU", "ABC", "F. Sugerida", "F. Necesidad", "Stock", "Demanda", "Pedir", "Lead time", "Estado", ""].map(h => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ocs.map((oc, i) => {
                const est = ESTADO_COLOR[oc.estado] || ESTADO_COLOR.pendiente
                return (
                  <tr key={oc.id} style={{ background: i % 2 === 0 ? "transparent" : "#0a111c" }}>
                    <td style={tdStyle}>
                      <code style={{ fontSize: 11 }}>{oc.sku}</code>
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>
                      <span style={{ color: ABC_COLOR[oc.clase_abc] || "#94a3b8", fontWeight: 700 }}>
                        {oc.clase_abc || "—"}
                      </span>
                    </td>
                    <td style={tdStyle}>{fmtDate(oc.fecha_sugerida)}</td>
                    <td style={tdStyle}>{fmtDate(oc.fecha_necesidad)}</td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      <span style={{ color: Number(oc.stock_actual) < 10 ? "#ef4444" : "#94a3b8" }}>
                        {fmt(oc.stock_actual)}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>{fmt(Math.round(oc.forecast_demanda))}</td>
                    <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700, fontSize: 14 }}>
                      <span style={{ color: "#e2e8f0" }}>{fmt(oc.cantidad_sugerida)}</span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>
                      <span style={{ color: "#64748b" }}>{oc.lead_time_dias}d</span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 11, background: est.bg, color: est.text, border: `1px solid ${est.border}`, padding: "2px 8px", borderRadius: 10 }}>
                        {oc.estado}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      {oc.estado === "pendiente" && (
                        <div style={{ display: "flex", gap: 4 }}>
                          <button onClick={() => cambiarEstado(oc.id, "aprobada")} style={{ ...btnSmStyle, background: "#052e16", color: "#4ade80", border: "1px solid #166534" }}>✓</button>
                          <button onClick={() => cambiarEstado(oc.id, "rechazada")} style={{ ...btnSmStyle, background: "#1c0a0a", color: "#f87171", border: "1px solid #7f1d1d" }}>✕</button>
                        </div>
                      )}
                      {oc.estado === "aprobada" && (
                        <button onClick={() => cambiarEstado(oc.id, "emitida")} style={{ ...btnSmStyle, background: "#1c1207", color: "#fbbf24", border: "1px solid #78350f" }}>Emitir</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value }) {
  return (
    <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 6, padding: "6px 14px", minWidth: 120 }}>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>{value}</div>
    </div>
  )
}

const thStyle  = { padding: "8px 10px", textAlign: "left", color: "#64748b", fontSize: 12, fontWeight: 600, borderBottom: "1px solid #1e2a3a", whiteSpace: "nowrap" }
const tdStyle  = { padding: "8px 10px", fontSize: 13, borderBottom: "1px solid #0f1a28", whiteSpace: "nowrap" }
const selStyle = { background: "#0d1520", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "5px 10px", fontSize: 13 }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }
const btnSmStyle   = { borderRadius: 5, padding: "3px 10px", fontSize: 12, cursor: "pointer" }
