import { useState, useEffect } from "react"
import { getAlertasQuiebre } from "../../services/api"
const API = "/api"

const hoy = new Date().toISOString().split("T")[0]

function fmt(n) { return n?.toLocaleString("es-CL") ?? "—" }

export default function AlertasPage() {
  const [alertas,         setAlertas]         = useState([])
  const [descontinuar,    setDescontinuar]    = useState([])
  const [loading,         setLoading]         = useState(false)
  const [msg,             setMsg]             = useState(null)
  const [fechaCorte, setFechaCorte] = useState(hoy)

  useEffect(() => { cargar() }, [])

  async function cargar() {
    setLoading(true)
    setMsg(null)
    try {
      const params = {}
      if (fechaCorte) params.fecha_corte = fechaCorte
      const [data, desc] = await Promise.all([
        getAlertasQuiebre(params),
        fetch(`${API}/ajuste-forecast/alertas-descontinuar`).then(r => r.ok ? r.json() : []),
      ])
      setAlertas(data)
      setDescontinuar(desc)
    } catch (e) {
      setMsg(e.message)
    } finally {
      setLoading(false)
    }
  }

  const criticos    = alertas.filter(a => a.nivel === "CRITICO")
  const advertencias = alertas.filter(a => a.nivel === "ADVERTENCIA")

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Alertas de Quiebre</div>
          <div className="page-subtitle">
            Productos en riesgo de agotarse durante su temporada activa — Lead time 90-120 días
          </div>
        </div>
        <div className="header-actions">
          <button className="btn btn-primary" onClick={cargar} disabled={loading}>
            {loading ? <span className="spinner" /> : "↻"}
            {loading ? "Analizando..." : "Actualizar"}
          </button>
        </div>
      </div>

      <div className="page-body">
        {msg && <div className="alert alert-error">{msg}</div>}

        {/* Filtro fecha */}
        <div className="card" style={{ marginBottom: 20, padding: "14px 20px" }}>
          <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
            <div className="form-group" style={{ minWidth: 180 }}>
              <label className="form-label">Fecha de corte</label>
              <input type="date" className="form-input" value={fechaCorte}
                onChange={e => setFechaCorte(e.target.value)} />
            </div>
            <button className="btn btn-secondary" onClick={cargar} disabled={loading}>Aplicar</button>
          </div>
        </div>

        {/* Stats */}
        <div className="stats-row">
          <div className="stat-card" style={{ borderColor: criticos.length ? "var(--danger)" : "var(--border)" }}>
            <div className="stat-value" style={{ color: criticos.length ? "var(--danger)" : "var(--text2)" }}>
              {criticos.length}
            </div>
            <div className="stat-label">Críticos</div>
            <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 4 }}>Producto estacional sin stock suficiente</div>
          </div>
          <div className="stat-card" style={{ borderColor: advertencias.length ? "var(--warn)" : "var(--border)" }}>
            <div className="stat-value" style={{ color: advertencias.length ? "var(--warn)" : "var(--text2)" }}>
              {advertencias.length}
            </div>
            <div className="stat-label">Advertencias</div>
            <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 4 }}>Menos de 8 semanas de stock restante</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{alertas.length}</div>
            <div className="stat-label">Total alertas</div>
          </div>
          <div className="stat-card" style={{ borderColor: descontinuar.length ? "#7c3aed" : "var(--border)" }}>
            <div className="stat-value" style={{ color: descontinuar.length ? "#7c3aed" : "var(--text2)" }}>
              {descontinuar.length}
            </div>
            <div className="stat-label">Para descontinuar</div>
            <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 4 }}>Stock en 0 y marcado Descontinuar</div>
          </div>
        </div>

        {alertas.length === 0 && !loading ? (
          <div className="empty-state">
            <div className="empty-icon">✓</div>
            <div style={{ color: "var(--accent2)", fontWeight: 500 }}>Sin alertas de quiebre</div>
            <div style={{ marginTop: 6, fontSize: 12 }}>Todos los productos tienen cobertura suficiente.</div>
          </div>
        ) : (
          <>
            {/* Tabla Críticos */}
            {criticos.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div className="alerta-seccion-header critico">
                  ⛔ Críticos ({criticos.length})
                </div>
                <AlertaTabla alertas={criticos} />
              </div>
            )}

            {/* Tabla Advertencias */}
            {advertencias.length > 0 && (
              <div>
                <div className="alerta-seccion-header advertencia">
                  ⚠ Advertencias ({advertencias.length})
                </div>
                <AlertaTabla alertas={advertencias} />
              </div>
            )}

            {/* Tabla Descontinuar */}
            {descontinuar.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div className="alerta-seccion-header" style={{ background: "rgba(124,58,237,0.12)", color: "#7c3aed", borderLeft: "3px solid #7c3aed" }}>
                  ⊟ Para descontinuar ({descontinuar.length}) — Stock agotado
                </div>
                <div className="card" style={{ padding: 0 }}>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Descripción</th>
                          <th>Marca</th>
                          <th style={{ textAlign: "right" }}>Stock Total</th>
                          <th>Acción sugerida</th>
                        </tr>
                      </thead>
                      <tbody>
                        {descontinuar.map(d => (
                          <tr key={d.sku}>
                            <td className="td-mono">{d.sku}</td>
                            <td style={{ color: "var(--text2)", fontSize: 12 }}>{d.descripcion || "—"}</td>
                            <td><span className="badge badge-blue">{d.marca || "—"}</span></td>
                            <td style={{ textAlign: "right", fontFamily: "var(--mono)", color: "var(--danger)" }}>0</td>
                            <td style={{ fontSize: 12, color: "#7c3aed", fontWeight: 600 }}>Marcar como Inactivo</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function AlertaTabla({ alertas }) {
  return (
    <div className="card" style={{ padding: 0 }}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Descripción</th>
              <th>Temporada</th>
              <th style={{ textAlign: "right" }}>Stock Total</th>
              <th style={{ textAlign: "right" }}>Avg/Sem</th>
              <th style={{ textAlign: "right" }}>Sem. Restantes</th>
              <th style={{ textAlign: "center" }}>Compra a tiempo</th>
              <th>Meses sin stock</th>
            </tr>
          </thead>
          <tbody>
            {alertas.map(a => (
              <tr key={a.sku}>
                <td className="td-mono">{a.sku}</td>
                <td style={{ color: "var(--text2)", fontSize: 12 }}>{a.descripcion || "—"}</td>
                <td>
                  <span className={`badge ${
                    a.temporada === "Verano" ? "badge-orange" :
                    a.temporada === "Invierno" ? "badge-blue" :
                    a.temporada === "No Estacional" ? "badge-green" : "badge-purple"
                  }`}>{a.temporada}</span>
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--mono)" }}>
                  {a.stock_total.toLocaleString("es-CL")}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--mono)" }}>
                  {a.weekly_avg_neto}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--mono)" }}>
                  {a.semanas_restantes_stock !== null
                    ? <span style={{ color: a.semanas_restantes_stock < 4 ? "var(--danger)" : "var(--warn)" }}>
                        {a.semanas_restantes_stock} sem.
                      </span>
                    : <span style={{ color: "var(--text3)" }}>sin datos</span>
                  }
                </td>
                <td style={{ textAlign: "center" }}>
                  {a.puede_comprar
                    ? <span style={{ color: "var(--accent2)", fontWeight: 600 }}>✓ Sí</span>
                    : <span style={{ color: "var(--danger)", fontWeight: 600 }}>✗ No</span>
                  }
                </td>
                <td>
                  {a.meses_sin_stock.length > 0
                    ? <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {a.meses_sin_stock.map(m => (
                          <span key={m} className="badge" style={{ background: "rgba(255,79,106,0.15)", color: "var(--danger)", fontSize: 10 }}>
                            {m}
                          </span>
                        ))}
                      </div>
                    : <span style={{ color: "var(--text3)", fontSize: 12 }}>—</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
