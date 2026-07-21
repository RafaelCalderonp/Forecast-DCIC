import { useState, useEffect, useMemo } from "react"
import { getProyeccion, getTemporadas, aplicarProyeccion } from "../../services/api"

const hoy = new Date().toISOString().split("T")[0]

const TEMP_COLORES = {
  "Verano":          "badge-orange",
  "Invierno":        "badge-blue",
  "No Estacional":   "badge-green",
  "Verano/Rotativo": "badge-purple",
}

function fmt(n) { return n?.toLocaleString("es-CL") ?? "—" }
function signo(n) { return n > 0 ? `+${fmt(n)}` : fmt(n) }

export default function AjusteForecastPage({ sinHeader = false }) {
  const [proyecciones, setProyecciones]   = useState([])
  const [temporadas,   setTemporadas]     = useState([])
  const [loading,      setLoading]        = useState(false)
  const [aplicando,    setAplicando]      = useState(false)
  const [msg,          setMsg]            = useState(null)
  const [expandidos,   setExpandidos]     = useState({})
  const [seleccionados, setSeleccionados] = useState({})  // key: "sku|anio|mes" → item
  const [filtros, setFiltros] = useState({ fecha_corte: hoy, temporada_nombre: "" })

  useEffect(() => {
    getTemporadas().then(setTemporadas).catch(() => {})
    cargar()
  }, [])

  async function cargar() {
    setLoading(true)
    setMsg(null)
    try {
      const params = {}
      if (filtros.fecha_corte)      params.fecha_corte      = filtros.fecha_corte
      if (filtros.temporada_nombre) params.temporada_nombre = filtros.temporada_nombre
      const data = await getProyeccion(params)
      setProyecciones(data)
      setSeleccionados({})
      setExpandidos({})
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  function toggleExpand(sku) {
    setExpandidos(p => ({ ...p, [sku]: !p[sku] }))
  }

  function toggleMes(sku, anio, mes, cantidad) {
    const key = `${sku}|${anio}|${mes}`
    setSeleccionados(p => {
      const next = { ...p }
      if (next[key]) delete next[key]
      else next[key] = { sku, anio, mes, cantidad }
      return next
    })
  }

  function selectAllSku(proy) {
    const keys = proy.proyecciones.map(m => `${proy.sku}|${m.anio}|${m.mes}`)
    const todosSelected = keys.every(k => seleccionados[k])
    setSeleccionados(p => {
      const next = { ...p }
      if (todosSelected) keys.forEach(k => delete next[k])
      else proy.proyecciones.forEach(m => {
        next[`${proy.sku}|${m.anio}|${m.mes}`] = { sku: proy.sku, anio: m.anio, mes: m.mes, cantidad: m.proyeccion }
      })
      return next
    })
  }

  function selectAll() {
    const allSel = proyecciones.every(p =>
      p.proyecciones.every(m => seleccionados[`${p.sku}|${m.anio}|${m.mes}`])
    )
    if (allSel) {
      setSeleccionados({})
    } else {
      const next = {}
      proyecciones.forEach(p => p.proyecciones.forEach(m => {
        next[`${p.sku}|${m.anio}|${m.mes}`] = { sku: p.sku, anio: m.anio, mes: m.mes, cantidad: m.proyeccion }
      }))
      setSeleccionados(next)
    }
  }

  async function aplicar() {
    const items = Object.values(seleccionados)
    if (!items.length) return
    setAplicando(true)
    setMsg(null)
    try {
      const res = await aplicarProyeccion(items)
      const creados     = res.filter(r => r.accion === "creado").length
      const actualizados = res.filter(r => r.accion === "actualizado").length
      setMsg({ tipo: "success", texto: `✓ ${creados} creados, ${actualizados} actualizados, ${res.filter(r => r.accion === "sin_cambio").length} sin cambio.` })
      setSeleccionados({})
      cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setAplicando(false)
    }
  }

  const stats = useMemo(() => {
    const conDatos   = proyecciones.filter(p => p.ventas_6s_neto > 0).length
    const conDif     = proyecciones.filter(p => p.proyecciones.some(m => m.diferencia !== 0)).length
    const conAdvert  = proyecciones.filter(p => p.advertencia).length
    const totalDif   = proyecciones.reduce((acc, p) => acc + p.proyecciones.reduce((a, m) => a + m.diferencia, 0), 0)
    return { conDatos, conDif, conAdvert, totalDif }
  }, [proyecciones])

  const nSel = Object.keys(seleccionados).length

  return (
    <div>
      {/* Header — título solo cuando es página standalone */}
      <div className="page-header">
        <div>
          {!sinHeader && <div className="page-title">Ajuste de Forecast</div>}
          {!sinHeader && <div className="page-subtitle">Proyección basada en ventas netas de las últimas 6 semanas</div>}
        </div>
        <div className="header-actions">
          {nSel > 0 && (
            <button className="btn btn-success" onClick={aplicar} disabled={aplicando}>
              {aplicando ? <span className="spinner" /> : "◈"}
              {aplicando ? "Aplicando..." : `Aplicar ${nSel} seleccionados`}
            </button>
          )}
          <button className="btn btn-primary" onClick={cargar} disabled={loading}>
            {loading ? <span className="spinner" /> : "↻"}
            {loading ? "Calculando..." : "Recalcular"}
          </button>
        </div>
      </div>

      <div className="page-body">
        {msg && (
          <div className={`alert alert-${msg.tipo === "error" ? "error" : "success"}`}>
            {msg.texto}
          </div>
        )}

        {/* Filtros */}
        <div className="card" style={{ marginBottom: 20, padding: "16px 20px" }}>
          <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
            <div className="form-group" style={{ minWidth: 180 }}>
              <label className="form-label">Fecha de corte</label>
              <input type="date" className="form-input" value={filtros.fecha_corte}
                onChange={e => setFiltros(p => ({ ...p, fecha_corte: e.target.value }))} />
            </div>
            <div className="form-group" style={{ minWidth: 200 }}>
              <label className="form-label">Temporada</label>
              <select className="form-select" value={filtros.temporada_nombre}
                onChange={e => setFiltros(p => ({ ...p, temporada_nombre: e.target.value }))}>
                <option value="">Todas</option>
                {temporadas.map(t => <option key={t.id} value={t.nombre}>{t.nombre}</option>)}
              </select>
            </div>
            <button className="btn btn-secondary" onClick={cargar} disabled={loading}>Filtrar</button>
          </div>
        </div>

        {/* Stats */}
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-value">{proyecciones.length}</div>
            <div className="stat-label">SKUs analizados</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--accent2)" }}>{stats.conDatos}</div>
            <div className="stat-label">Con ventas últimas 6 sem.</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.totalDif > 0 ? "var(--accent)" : "var(--danger)" }}>
              {signo(stats.totalDif)}
            </div>
            <div className="stat-label">Diferencia total (uds.)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.conDif > 0 ? "var(--accent)" : "var(--text2)" }}>{stats.conDif}</div>
            <div className="stat-label">SKUs con diferencia</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: "var(--warn)" }}>{stats.conAdvert}</div>
            <div className="stat-label">Con advertencias</div>
          </div>
        </div>

        {/* Tabla principal */}
        {loading && proyecciones.length === 0 ? (
          <div className="empty-state">
            <span className="spinner" style={{ width: 28, height: 28, borderWidth: 3 }} />
            <div style={{ marginTop: 14 }}>Calculando proyecciones...</div>
          </div>
        ) : proyecciones.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">◎</div>
            <div>No hay datos. Haz clic en Recalcular.</div>
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
              <input type="checkbox"
                checked={proyecciones.length > 0 && proyecciones.every(p =>
                  p.proyecciones.every(m => seleccionados[`${p.sku}|${m.anio}|${m.mes}`])
                )}
                onChange={selectAll}
                style={{ width: 15, height: 15, cursor: "pointer" }}
              />
              <span style={{ fontSize: 12, color: "var(--text2)" }}>Seleccionar todo</span>
            </div>

            {proyecciones.map(proy => {
              const abierto  = expandidos[proy.sku]
              const todosSel = proy.proyecciones.every(m => seleccionados[`${proy.sku}|${m.anio}|${m.mes}`])
              const algSel   = proy.proyecciones.some(m => seleccionados[`${proy.sku}|${m.anio}|${m.mes}`])

              return (
                <div key={proy.sku} className="forecast-sku-block">
                  {/* Fila SKU */}
                  <div className="forecast-sku-row" onClick={() => toggleExpand(proy.sku)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }} onClick={e => e.stopPropagation()}>
                      <input type="checkbox"
                        checked={todosSel}
                        ref={el => { if (el) el.indeterminate = !todosSel && algSel }}
                        onChange={() => selectAllSku(proy)}
                        style={{ width: 15, height: 15, cursor: "pointer" }}
                      />
                    </div>

                    <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
                      <span className="td-mono" style={{ fontSize: 13 }}>{proy.sku}</span>
                      <span style={{ color: "var(--text2)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {proy.descripcion || "—"}
                      </span>
                    </div>

                    <div style={{ display: "flex", gap: 10, alignItems: "center", flexShrink: 0 }}>
                      <span className={`badge ${TEMP_COLORES[proy.temporada] || "badge-gray"}`}>
                        {proy.temporada}
                      </span>
                      {!proy.en_temporada_activa && (
                        <span className="badge badge-gray" style={{ fontSize: 10 }}>fuera de temporada</span>
                      )}
                      <div style={{ textAlign: "right", minWidth: 90 }}>
                        <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--text)" }}>
                          {fmt(proy.weekly_avg_neto)} u/sem
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text2)" }}>
                          {fmt(proy.ventas_6s_neto)} neto 6 sem
                        </div>
                      </div>
                      {proy.advertencia && (
                        <span title={proy.advertencia} style={{ color: "var(--warn)", fontSize: 16, cursor: "help" }}>⚠</span>
                      )}
                      <span style={{ color: "var(--text3)", fontSize: 18, marginLeft: 4 }}>
                        {abierto ? "▾" : "▸"}
                      </span>
                    </div>
                  </div>

                  {/* Detalle mensual */}
                  {abierto && (
                    <div className="forecast-meses">
                      {proy.advertencia && (
                        <div className="alert alert-info" style={{ margin: "12px 16px 0", padding: "8px 12px", fontSize: 12 }}>
                          ⚠ {proy.advertencia}
                        </div>
                      )}
                      <table style={{ margin: "12px 0 4px" }}>
                        <thead>
                          <tr>
                            <th style={{ width: 40 }}></th>
                            <th>Mes</th>
                            <th style={{ textAlign: "right" }}>FC Actual</th>
                            <th style={{ textAlign: "right" }}>Proyección</th>
                            <th style={{ textAlign: "right" }}>Diferencia</th>
                            <th style={{ textAlign: "center" }}>Compra OK</th>
                          </tr>
                        </thead>
                        <tbody>
                          {proy.proyecciones.map(m => {
                            const key  = `${proy.sku}|${m.anio}|${m.mes}`
                            const sel  = !!seleccionados[key]
                            const dif  = m.diferencia
                            const clr  = dif > 0 ? "var(--accent)" : dif < 0 ? "var(--danger)" : "var(--text2)"
                            return (
                              <tr key={key} className={sel ? "row-selected" : ""} onClick={() => toggleMes(proy.sku, m.anio, m.mes, m.proyeccion)} style={{ cursor: "pointer" }}>
                                <td onClick={e => e.stopPropagation()} style={{ textAlign: "center" }}>
                                  <input type="checkbox" checked={sel}
                                    onChange={() => toggleMes(proy.sku, m.anio, m.mes, m.proyeccion)}
                                    style={{ cursor: "pointer" }} />
                                </td>
                                <td style={{ fontWeight: 500 }}>{m.nombre_mes} {m.anio}</td>
                                <td style={{ textAlign: "right", fontFamily: "var(--mono)" }}>{fmt(m.forecast_actual)}</td>
                                <td style={{ textAlign: "right", fontFamily: "var(--mono)", color: "var(--accent2)" }}>{fmt(m.proyeccion)}</td>
                                <td style={{ textAlign: "right", fontFamily: "var(--mono)", color: clr, fontWeight: 600 }}>{signo(dif)}</td>
                                <td style={{ textAlign: "center" }}>
                                  {m.puede_comprar
                                    ? <span style={{ color: "var(--accent2)" }}>✓</span>
                                    : <span style={{ color: "var(--danger)" }}>✗</span>}
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
            })}
          </div>
        )}
      </div>
    </div>
  )
}
