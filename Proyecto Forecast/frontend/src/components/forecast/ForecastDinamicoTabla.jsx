import { useState, useEffect, useCallback } from "react"
import { getForecastResumen, calcularForecast, refreshVistaForecast } from "../../services/api"

const API = "/api"

function fmt(n, dec = 0) {
  if (n == null) return "—"
  return Number(n).toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtPct(n) {
  if (n == null) return "—"
  return (Number(n) * 100).toFixed(1) + "%"
}
function claseColor(abc) {
  if (abc === "A") return "#22c55e"
  if (abc === "B") return "#f59e0b"
  return "#94a3b8"
}
function mapeColor(estado) {
  if (estado === "bueno")   return "#22c55e"
  if (estado === "regular") return "#f59e0b"
  if (estado === "malo")    return "#ef4444"
  return "#94a3b8"
}

const PERIODOS_OPCIONES = (() => {
  const meses = []
  const hoy = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(hoy.getFullYear(), hoy.getMonth() + i, 1)
    meses.push({
      value: d.toISOString().split("T")[0],
      label: d.toLocaleDateString("es-CL", { month: "short", year: "numeric" }),
    })
  }
  return meses
})()

export default function ForecastDinamicoTabla() {
  const [data,        setData]        = useState([])
  const [total,       setTotal]       = useState(0)
  const [page,        setPage]        = useState(1)
  const [loading,     setLoading]     = useState(false)
  const [calculating, setCalculating] = useState(false)
  const [msg,         setMsg]         = useState(null)
  const [filtros, setFiltros] = useState({
    periodo:    PERIODOS_OPCIONES[0].value,
    canal:      "",
    clase_abc:  "",
    estado_mape: "",
  })

  const cargar = useCallback(async (p = page) => {
    setLoading(true)
    setMsg(null)
    try {
      const params = { page: p, per_page: 50 }
      if (filtros.periodo)     params.periodo      = filtros.periodo
      if (filtros.canal)       params.canal        = filtros.canal
      if (filtros.clase_abc)   params.clase_abc    = filtros.clase_abc
      if (filtros.estado_mape) params.estado_mape  = filtros.estado_mape
      const res = await getForecastResumen(params)
      setData(res.data || [])
      setTotal(res.total || 0)
      setPage(p)
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }, [filtros, page])

  useEffect(() => { cargar(1) }, [filtros]) // eslint-disable-line

  async function handleCalcular() {
    if (!window.confirm("¿Recalcular forecast HW para TODOS los SKUs activos? Puede tardar 1-2 minutos.")) return
    setCalculating(true)
    setMsg(null)
    try {
      await calcularForecast()
      setMsg({ tipo: "ok", texto: "Cálculo iniciado en background. Refresca en ~60s." })
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setCalculating(false)
    }
  }

  async function handleRefresh() {
    setLoading(true)
    try {
      await refreshVistaForecast()
      await cargar(page)
      setMsg({ tipo: "ok", texto: "Vista actualizada" })
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  function handleExportCsv() {
    const token = localStorage.getItem("dcic_token") || ""
    const p = filtros.periodo || PERIODOS_OPCIONES[0].value
    // periodo_inicio = primer día del mes, periodo_fin = último día
    const d = new Date(p)
    const fin = new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().split("T")[0]
    let url = `/api/forecast-dinamico/export/csv?periodo_inicio=${p}&periodo_fin=${fin}`
    if (filtros.canal) url += `&canal=${encodeURIComponent(filtros.canal)}`
    // Descarga via fetch para incluir Authorization header
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const a = document.createElement("a")
        a.href = URL.createObjectURL(blob)
        a.download = `forecast_${p.slice(0, 7)}.csv`
        a.click()
        URL.revokeObjectURL(a.href)
      })
      .catch(e => setMsg({ tipo: "error", texto: e.message }))
  }

  const pages = Math.ceil(total / 50)

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      {/* Toolbar */}
      <div style={{ padding: "10px 16px", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", borderBottom: "1px solid #1e2a3a", flexShrink: 0 }}>
        {/* Filtros */}
        <select
          value={filtros.periodo}
          onChange={e => setFiltros(f => ({ ...f, periodo: e.target.value }))}
          style={selStyle}
        >
          {PERIODOS_OPCIONES.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <select value={filtros.canal} onChange={e => setFiltros(f => ({ ...f, canal: e.target.value }))} style={selStyle}>
          <option value="">Todos los canales</option>
          <option value="Mercado Libre">Mercado Libre</option>
          <option value="Tienda Propia">Tienda Propia</option>
          <option value="Ripley">Ripley</option>
          <option value="Falabella">Falabella</option>
          <option value="Paris">Paris</option>
        </select>

        <select value={filtros.clase_abc} onChange={e => setFiltros(f => ({ ...f, clase_abc: e.target.value }))} style={selStyle}>
          <option value="">ABC: todos</option>
          <option value="A">A — Top 70%</option>
          <option value="B">B — 70-90%</option>
          <option value="C">C — resto</option>
        </select>

        <select value={filtros.estado_mape} onChange={e => setFiltros(f => ({ ...f, estado_mape: e.target.value }))} style={selStyle}>
          <option value="">MAPE: todos</option>
          <option value="bueno">Bueno (&lt;15%)</option>
          <option value="regular">Regular (15-30%)</option>
          <option value="malo">Malo (&gt;30%)</option>
        </select>

        <span style={{ flex: 1 }} />

        <button onClick={handleExportCsv} style={btnSecStyle} title="Exportar período seleccionado como CSV">
          ⬇ CSV
        </button>
        <button onClick={handleRefresh} disabled={loading} style={btnSecStyle}>
          ↻ Refrescar
        </button>
        <button onClick={handleCalcular} disabled={calculating} style={btnPrimStyle}>
          {calculating ? "Calculando…" : "⚡ Recalcular HW"}
        </button>
      </div>

      {/* Mensaje */}
      {msg && (
        <div style={{
          margin: "6px 16px", padding: "8px 12px", borderRadius: 6, fontSize: 13,
          background: msg.tipo === "ok" ? "#052e16" : "#1c0a0a",
          color: msg.tipo === "ok" ? "#4ade80" : "#f87171",
          border: `1px solid ${msg.tipo === "ok" ? "#166534" : "#7f1d1d"}`,
        }}>
          {msg.texto}
        </div>
      )}

      {/* KPIs rápidos */}
      <div style={{ padding: "8px 16px", display: "flex", gap: 12, flexShrink: 0 }}>
        <Kpi label="Registros" value={fmt(total)} />
        <Kpi label="Página" value={`${page} / ${pages || 1}`} />
      </div>

      {/* Tabla */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "auto" }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Cargando…</div>
        ) : data.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
            Sin datos para este período. Usa "⚡ Recalcular HW" para generar el forecast.
          </div>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: "#0d1520" }}>
                <Th>SKU</Th>
                <Th>Canal</Th>
                <Th>Período</Th>
                <Th>ABC</Th>
                <Th>XYZ</Th>
                <Th right>F. Base</Th>
                <Th right>Lift ×</Th>
                <Th right>F. Ajustado</Th>
                <Th right>F. Final</Th>
                <Th right>DCI días</Th>
                <Th right>V. Reales</Th>
                <Th right>MAPE</Th>
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : "#0a111c" }}>
                  <td style={tdStyle}><span style={{ fontFamily: "monospace", fontSize: 12 }}>{r.sku}</span></td>
                  <td style={tdStyle}>{r.canal}</td>
                  <td style={tdStyle}>{r.periodo ? r.periodo.slice(0, 7) : "—"}</td>
                  <td style={{ ...tdStyle, textAlign: "center" }}>
                    <span style={{ color: claseColor(r.clase_abc), fontWeight: 700 }}>{r.clase_abc ?? "—"}</span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: "center" }}>
                    <span style={{ color: "#94a3b8" }}>{r.clase_xyz ?? "—"}</span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>{fmt(r.forecast_base, 0)}</td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <span style={{ color: Number(r.lift_aplicado) > 1 ? "#f59e0b" : "#94a3b8" }}>
                      ×{Number(r.lift_aplicado ?? 1).toFixed(2)}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>{fmt(r.forecast_ajustado, 0)}</td>
                  <td style={{ ...tdStyle, textAlign: "right", fontWeight: 600 }}>{fmt(r.forecast_final, 0)}</td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <span style={{ color: Number(r.dci) < 30 ? "#ef4444" : "#94a3b8" }}>
                      {r.dci != null ? Number(r.dci).toFixed(1) : "—"}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", color: "#64748b" }}>{fmt(r.ventas_reales, 0)}</td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <span style={{ color: mapeColor(r.estado_mape) }}>
                      {r.mape != null ? fmtPct(r.mape) : "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Paginación */}
      {pages > 1 && (
        <div style={{ padding: "8px 16px", display: "flex", gap: 8, justifyContent: "center", borderTop: "1px solid #1e2a3a", flexShrink: 0 }}>
          <button onClick={() => cargar(1)}       disabled={page === 1}     style={btnSecStyle}>«</button>
          <button onClick={() => cargar(page - 1)} disabled={page === 1}    style={btnSecStyle}>‹</button>
          <span style={{ color: "#94a3b8", fontSize: 13, padding: "4px 8px" }}>
            Pág {page} / {pages} ({fmt(total)} filas)
          </span>
          <button onClick={() => cargar(page + 1)} disabled={page === pages} style={btnSecStyle}>›</button>
          <button onClick={() => cargar(pages)}    disabled={page === pages} style={btnSecStyle}>»</button>
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value }) {
  return (
    <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 6, padding: "6px 14px", minWidth: 100 }}>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0" }}>{value}</div>
    </div>
  )
}

function Th({ children, right }) {
  return (
    <th style={{ padding: "8px 10px", textAlign: right ? "right" : "left", color: "#64748b", fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", position: "sticky", top: 0, background: "#0d1520", zIndex: 1 }}>
      {children}
    </th>
  )
}

const tdStyle = { padding: "7px 10px", fontSize: 13, borderBottom: "1px solid #0f1a28", whiteSpace: "nowrap" }
const tableStyle = { width: "100%", borderCollapse: "collapse", fontSize: 13 }
const selStyle = { background: "#0d1520", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "5px 10px", fontSize: 13 }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }
const btnSecStyle = { background: "#1e2a3a", color: "#94a3b8", border: "1px solid #2a3a4a", borderRadius: 6, padding: "5px 12px", fontSize: 13, cursor: "pointer" }
