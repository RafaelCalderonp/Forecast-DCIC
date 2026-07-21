import { useState, useEffect } from "react"
import { getSegmentacion, recalcularSegmentacion } from "../../services/api"

const CLASES = ["A", "B", "C"]
const VARIAB  = ["X", "Y", "Z"]

const DESC_ABC = { A: "Top 70% revenue", B: "70–90% revenue", C: "Resto" }
const DESC_XYZ = { X: "Demanda estable (CV<0.5)", Y: "Variable (CV 0.5–1)", Z: "Irregular (CV>1)" }

const COLOR_ABC = { A: "#22c55e", B: "#f59e0b", C: "#94a3b8" }
const BG_CELDA  = {
  AX: "#052e16", AY: "#064e3b", AZ: "#134e4a",
  BX: "#1e1b4b", BY: "#312e81", BZ: "#3730a3",
  CX: "#1c1917", CY: "#292524", CZ: "#1c1917",
}

function fmt(n) { return n?.toLocaleString("es-CL") ?? "—" }

// Período por defecto: últimos 12 meses
const hoy  = new Date()
const hace12 = new Date(hoy.getFullYear() - 1, hoy.getMonth(), 1)
const PER_INI_DEFAULT = hace12.toISOString().slice(0, 10)
const PER_FIN_DEFAULT = new Date(hoy.getFullYear(), hoy.getMonth(), 0).toISOString().slice(0, 10)

export default function SegmentacionPanel() {
  const [matriz,    setMatriz]    = useState({})
  const [totalSkus, setTotalSkus] = useState(0)
  const [canal,     setCanal]     = useState("")
  const [loading,   setLoading]   = useState(false)
  const [recalc,    setRecalc]    = useState(false)
  const [msg,       setMsg]       = useState(null)
  const [perIni,    setPerIni]    = useState(PER_INI_DEFAULT)
  const [perFin,    setPerFin]    = useState(PER_FIN_DEFAULT)
  const [selCelda,  setSelCelda]  = useState(null)   // "AX", "BZ", etc.

  useEffect(() => { cargar() }, [canal]) // eslint-disable-line

  async function cargar() {
    setLoading(true)
    setMsg(null)
    try {
      const res = await getSegmentacion(canal)
      setMatriz(res.matriz || {})
      setTotalSkus(res.total_skus || 0)
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  async function handleRecalcular() {
    if (!perIni || !perFin) { setMsg({ tipo: "error", texto: "Selecciona período inicio y fin" }); return }
    if (!window.confirm(`¿Recalcular segmentación ABC-XYZ para ${perIni} — ${perFin}?`)) return
    setRecalc(true)
    setMsg(null)
    try {
      const res = await recalcularSegmentacion(perIni, perFin)
      setMsg({ tipo: "ok", texto: `${res.skus_reclasificados} SKUs reclasificados` })
      await cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setRecalc(false)
    }
  }

  const skusEnCelda = selCelda ? (matriz[selCelda] || []) : []

  return (
    <div style={{ padding: 16 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <select value={canal} onChange={e => { setCanal(e.target.value); setSelCelda(null) }} style={selStyle}>
          <option value="">Todos los canales</option>
          <option value="Mercado Libre">Mercado Libre</option>
          <option value="Tienda Propia">Tienda Propia</option>
          <option value="Ripley">Ripley</option>
          <option value="Falabella">Falabella</option>
          <option value="Paris">Paris</option>
        </select>

        <span style={{ flex: 1 }} />

        <label style={labelStyle}>Recalcular período:</label>
        <input type="date" value={perIni} onChange={e => setPerIni(e.target.value)} style={{ ...selStyle, width: 140 }} />
        <span style={{ color: "#64748b" }}>→</span>
        <input type="date" value={perFin} onChange={e => setPerFin(e.target.value)} style={{ ...selStyle, width: 140 }} />
        <button onClick={handleRecalcular} disabled={recalc} style={btnPrimStyle}>
          {recalc ? "Calculando…" : "🔷 Recalcular"}
        </button>
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
        <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>Cargando…</div>
      ) : (
        <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* Heatmap 3×3 */}
          <div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 8 }}>
              Total SKUs: <strong style={{ color: "#e2e8f0" }}>{fmt(totalSkus)}</strong>
            </div>

            {/* Eje X header */}
            <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 1fr 1fr", marginBottom: 4 }}>
              <div />
              {VARIAB.map(v => (
                <div key={v} style={{ textAlign: "center", fontSize: 12, color: "#64748b", padding: "4px 0" }}>
                  <strong style={{ color: "#94a3b8" }}>{v}</strong><br/>
                  <span style={{ fontSize: 10 }}>{DESC_XYZ[v].split("(")[0].trim()}</span>
                </div>
              ))}
            </div>

            {CLASES.map(abc => (
              <div key={abc} style={{ display: "grid", gridTemplateColumns: "60px 1fr 1fr 1fr", marginBottom: 4 }}>
                {/* Eje Y */}
                <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", paddingRight: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: COLOR_ABC[abc] }}>{abc}</span>
                  <span style={{ fontSize: 10, color: "#64748b" }}>{DESC_ABC[abc]}</span>
                </div>
                {VARIAB.map(xyz => {
                  const clave = `${abc}${xyz}`
                  const skus = matriz[clave] || []
                  const activa = selCelda === clave
                  return (
                    <div
                      key={xyz}
                      onClick={() => setSelCelda(activa ? null : clave)}
                      style={{
                        background: BG_CELDA[clave] || "#0d1520",
                        border: activa ? "2px solid #3d7eff" : "1px solid #1e2a3a",
                        borderRadius: 8, padding: "10px 8px", textAlign: "center",
                        cursor: skus.length > 0 ? "pointer" : "default",
                        minWidth: 110, minHeight: 70,
                        transition: "border 0.15s",
                      }}
                    >
                      <div style={{ fontSize: 22, fontWeight: 800, color: "#e2e8f0" }}>{skus.length}</div>
                      <div style={{ fontSize: 11, color: "#94a3b8" }}>SKUs</div>
                      <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                        {fmt(skus.reduce((acc, s) => acc + (s.revenue || 0), 0)).slice(0, 8)}
                      </div>
                    </div>
                  )
                })}
              </div>
            ))}

            {/* Leyenda */}
            <div style={{ marginTop: 12, fontSize: 11, color: "#64748b", lineHeight: 1.8 }}>
              <strong style={{ color: "#94a3b8" }}>Interpretación:</strong><br/>
              🟢 <strong>AX</strong> = alta rotación + demanda estable → prioridad máxima<br/>
              🟡 <strong>AZ/BZ</strong> = alto revenue + demanda errática → gestión activa<br/>
              ⚪ <strong>CZ</strong> = bajo valor + irregular → candidatos a descontinuar
            </div>
          </div>

          {/* Detalle celda */}
          {selCelda && (
            <div style={{ flex: 1, minWidth: 260, maxWidth: 420 }}>
              <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 8, overflow: "hidden" }}>
                <div style={{ padding: "10px 14px", background: BG_CELDA[selCelda], borderBottom: "1px solid #1e2a3a" }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: "#e2e8f0" }}>Cuadrante {selCelda}</span>
                  <span style={{ marginLeft: 10, fontSize: 12, color: "#94a3b8" }}>{skusEnCelda.length} SKUs</span>
                </div>
                <div style={{ maxHeight: 360, overflowY: "auto" }}>
                  {skusEnCelda.length === 0 ? (
                    <div style={{ padding: 16, color: "#64748b", fontSize: 13 }}>Sin SKUs en este cuadrante</div>
                  ) : (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr>
                          <th style={thDetStyle}>SKU</th>
                          <th style={{ ...thDetStyle, textAlign: "right" }}>Revenue</th>
                        </tr>
                      </thead>
                      <tbody>
                        {skusEnCelda
                          .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
                          .slice(0, 50)
                          .map((s, i) => (
                            <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : "#060d14" }}>
                              <td style={tdDetStyle}><code style={{ fontSize: 11 }}>{s.sku}</code></td>
                              <td style={{ ...tdDetStyle, textAlign: "right", color: "#94a3b8" }}>
                                ${fmt(Math.round(s.revenue || 0))}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const selStyle   = { background: "#0d1520", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "5px 10px", fontSize: 13 }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }
const labelStyle = { fontSize: 12, color: "#64748b" }
const thDetStyle = { padding: "6px 10px", fontSize: 11, color: "#64748b", borderBottom: "1px solid #1e2a3a", textAlign: "left", position: "sticky", top: 0, background: "#0d1520" }
const tdDetStyle = { padding: "6px 10px", fontSize: 12, borderBottom: "1px solid #060d14" }
