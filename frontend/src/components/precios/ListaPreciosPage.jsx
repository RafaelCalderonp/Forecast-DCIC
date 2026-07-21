import { useState, useEffect, useRef } from "react"
import { useAuth } from "../../context/AuthContext"

const API = "/api"

function clp(n) {
  if (n == null || n === "") return "—"
  return "$" + Number(n).toLocaleString("es-CL", { maximumFractionDigits: 0 })
}

function UploadModal({ onClose, onSuccess, authFetch }) {
  const [file, setFile] = useState(null)
  const [descripcion, setDescripcion] = useState("")
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState(null)
  const fileRef = useRef()

  async function subir() {
    if (!file) return
    setLoading(true)
    setError(null)
    setResultado(null)
    try {
      const fd = new FormData()
      fd.append("file", file)
      fd.append("descripcion", descripcion)
      fd.append("usuario", "")
      const r = await authFetch(`${API}/lista-precios/upload`, { method: "POST", body: fd })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || JSON.stringify(data))
      setResultado(data)
      onSuccess?.()
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000
    }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div style={{
        background: "var(--surface)", borderRadius: 10, padding: 28,
        width: 480, maxWidth: "95vw", display: "flex", flexDirection: "column", gap: 16,
        boxShadow: "0 8px 32px rgba(0,0,0,0.28)"
      }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>↑ Subir nueva Lista de Precios</div>

        {/* Dropzone */}
        <div
          onClick={() => fileRef.current?.click()}
          style={{
            border: `2px dashed ${file ? "var(--accent2)" : "var(--border)"}`,
            borderRadius: 8, padding: "24px 16px", textAlign: "center",
            cursor: "pointer", transition: "border-color .2s",
            background: file ? "rgba(34,197,94,0.05)" : "transparent"
          }}
        >
          <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }}
            onChange={e => setFile(e.target.files[0])} />
          {file
            ? <><div style={{ fontWeight: 600, color: "var(--accent2)" }}>✓ {file.name}</div>
                <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 4 }}>
                  {(file.size / 1024).toFixed(1)} KB
                </div></>
            : <><div style={{ fontSize: 14, color: "var(--text2)" }}>Arrastra o haz clic para seleccionar</div>
                <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 4 }}>.xlsx / .xls</div></>
          }
        </div>

        {/* Descripción */}
        <div className="form-group">
          <label className="form-label">Descripción / versión (opcional)</label>
          <input className="form-input" value={descripcion}
            onChange={e => setDescripcion(e.target.value)}
            placeholder="ej: LP Julio 2026 con ajuste USD" />
        </div>

        {/* Resultado */}
        {resultado && (
          <div style={{
            background: "rgba(34,197,94,0.08)", border: "1px solid var(--accent2)",
            borderRadius: 8, padding: "12px 16px", fontSize: 13
          }}>
            <div style={{ fontWeight: 600, color: "var(--accent2)", marginBottom: 6 }}>
              ✓ LP cargada correctamente
            </div>
            <div><b>{resultado.n_skus}</b> SKUs procesados</div>
            <div><b>{resultado.n_actualizados}</b> precios actualizados</div>
            <div style={{ color: "var(--text2)", marginTop: 4 }}>
              Campos: {resultado.campos_detectados?.join(", ")}
            </div>
          </div>
        )}

        {error && (
          <div style={{
            background: "rgba(239,68,68,0.08)", border: "1px solid var(--danger)",
            borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "var(--danger)"
          }}>✗ {error}</div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onClose}>Cerrar</button>
          <button className="btn btn-primary" onClick={subir}
            disabled={!file || loading}>
            {loading ? <><span className="spinner" style={{ marginRight: 6 }} />Subiendo…</> : "↑ Cargar LP"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ListaPreciosPage() {
  const { authFetch } = useAuth()
  const [lp, setLp] = useState([])
  const [historial, setHistorial] = useState([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState("")
  const [showUpload, setShowUpload] = useState(false)
  const [tab, setTab] = useState("lp") // "lp" | "historial"

  async function cargar() {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        authFetch(`${API}/lista-precios/actual`).then(r => r.json()),
        authFetch(`${API}/lista-precios/historial`).then(r => r.json()),
      ])
      setLp(Array.isArray(r1) ? r1 : [])
      setHistorial(Array.isArray(r2) ? r2 : [])
    } catch (_) {}
    setLoading(false)
  }

  useEffect(() => { cargar() }, [])

  const filtrada = lp.filter(p => {
    if (!busqueda) return true
    const q = busqueda.toLowerCase()
    return p.sku?.toLowerCase().includes(q) ||
      p.descripcion?.toLowerCase().includes(q) ||
      p.marca?.toLowerCase().includes(q) ||
      p.categoria?.toLowerCase().includes(q)
  })

  const lpActiva = historial.find(h => h.activa)

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ fontWeight: 700, fontSize: 20, margin: 0 }}>💲 Lista de Precios</h2>
          {lpActiva && (
            <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 3 }}>
              Activa: <b style={{ color: "var(--accent)" }}>{lpActiva.nombre_archivo}</b>
              {lpActiva.descripcion && ` — ${lpActiva.descripcion}`}
              {" · "}
              {new Date(lpActiva.subido_en).toLocaleDateString("es-CL")}
              {" · "}
              {lpActiva.n_actualizados?.toLocaleString("es-CL")} precios actualizados
            </div>
          )}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
            ↑ Subir nueva LP
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 0, marginBottom: 16, borderBottom: "1px solid var(--border)" }}>
        {[["lp", `Lista actual (${lp.length})`], ["historial", `Historial (${historial.length})`]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: "8px 20px", fontSize: 13, fontWeight: tab === id ? 700 : 400,
            border: "none", background: "transparent", cursor: "pointer",
            borderBottom: tab === id ? "2px solid var(--accent)" : "2px solid transparent",
            color: tab === id ? "var(--accent)" : "var(--text2)",
          }}>{label}</button>
        ))}
      </div>

      {/* Tab: LP actual */}
      {tab === "lp" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <input className="form-input" value={busqueda}
              onChange={e => setBusqueda(e.target.value)}
              placeholder="Buscar por SKU, nombre, marca o categoría…"
              style={{ maxWidth: 360 }} />
          </div>

          {loading
            ? <div style={{ padding: 40, textAlign: "center", color: "var(--text2)" }}>Cargando…</div>
            : (
            <div style={{ overflowX: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "var(--surface2)", position: "sticky", top: 0 }}>
                    {["SKU", "Descripción", "Marca", "Categoría",
                      "P. Bruto", "P. Neto", "Costo Neto", "P. Mínimo Evento", "P. Liquidación"
                    ].map(h => (
                      <th key={h} style={{
                        padding: "8px 10px", textAlign: h.startsWith("P.") || h.startsWith("C") ? "right" : "left",
                        fontWeight: 600, fontSize: 11, whiteSpace: "nowrap",
                        borderBottom: "1px solid var(--border)"
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtrada.map((p, i) => (
                    <tr key={p.sku} style={{ background: i % 2 === 0 ? "transparent" : "var(--surface2)" }}>
                      <td style={{ padding: "5px 10px", fontFamily: "var(--mono)", fontWeight: 600, color: "var(--accent)", whiteSpace: "nowrap" }}>{p.sku}</td>
                      <td style={{ padding: "5px 10px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.descripcion}</td>
                      <td style={{ padding: "5px 10px", whiteSpace: "nowrap" }}>{p.marca || "—"}</td>
                      <td style={{ padding: "5px 10px", whiteSpace: "nowrap", fontSize: 11, color: "var(--text2)" }}>{p.categoria || "—"}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", fontFamily: "var(--mono)", fontWeight: 600 }}>{clp(p.precio_venta_bruto)}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", fontFamily: "var(--mono)" }}>{p.precio_venta_bruto ? clp(Math.round(p.precio_venta_bruto / 1.19 * 100) / 100) : "—"}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", fontFamily: "var(--mono)", color: "var(--text2)" }}>{clp(p.costo_unitario_neto)}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", fontFamily: "var(--mono)", color: "var(--warn)" }}>{clp(p.precio_minimo_evento)}</td>
                      <td style={{ padding: "5px 10px", textAlign: "right", fontFamily: "var(--mono)", color: "var(--danger)" }}>{clp(p.precio_liquidacion)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtrada.length === 0 && (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text2)" }}>
                  Sin resultados para "{busqueda}"
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Tab: Historial */}
      {tab === "historial" && (
        <div style={{ overflowX: "auto", borderRadius: 8, border: "1px solid var(--border)" }}>
          {historial.length === 0
            ? <div style={{ padding: 32, textAlign: "center", color: "var(--text2)", fontSize: 13 }}>
                Sin historial — sube tu primera LP con el botón de arriba
              </div>
            : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--surface2)" }}>
                  {["", "Archivo", "Descripción", "Fecha", "SKUs", "Actualizados", "Campos"].map(h => (
                    <th key={h} style={{
                      padding: "8px 12px", textAlign: "left", fontWeight: 600,
                      fontSize: 11, borderBottom: "1px solid var(--border)", whiteSpace: "nowrap"
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {historial.map((h, i) => (
                  <tr key={h.id} style={{
                    background: h.activa
                      ? "rgba(59,130,246,0.06)"
                      : i % 2 === 0 ? "transparent" : "var(--surface2)"
                  }}>
                    <td style={{ padding: "6px 12px", textAlign: "center" }}>
                      {h.activa && <span style={{ fontSize: 11, fontWeight: 700, color: "var(--accent)",
                        background: "rgba(59,130,246,0.12)", padding: "2px 8px", borderRadius: 20 }}>
                        ACTIVA
                      </span>}
                    </td>
                    <td style={{ padding: "6px 12px", fontFamily: "var(--mono)", fontSize: 12, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {h.nombre_archivo}
                    </td>
                    <td style={{ padding: "6px 12px", color: "var(--text2)", fontSize: 12 }}>
                      {h.descripcion || "—"}
                    </td>
                    <td style={{ padding: "6px 12px", whiteSpace: "nowrap", fontSize: 12 }}>
                      {new Date(h.subido_en).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" })}
                    </td>
                    <td style={{ padding: "6px 12px", textAlign: "right", fontFamily: "var(--mono)" }}>
                      {(h.n_skus || 0).toLocaleString("es-CL")}
                    </td>
                    <td style={{ padding: "6px 12px", textAlign: "right", fontFamily: "var(--mono)", fontWeight: 600, color: "var(--accent2)" }}>
                      {(h.n_actualizados || 0).toLocaleString("es-CL")}
                    </td>
                    <td style={{ padding: "6px 12px", fontSize: 11, color: "var(--text2)" }}>
                      {(h.campos_actualizados || []).join(", ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showUpload && (
        <UploadModal
          authFetch={authFetch}
          onClose={() => setShowUpload(false)}
          onSuccess={() => { setShowUpload(false); cargar() }}
        />
      )}
    </div>
  )
}
