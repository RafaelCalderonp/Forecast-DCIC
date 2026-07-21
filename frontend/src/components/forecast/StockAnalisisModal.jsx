import { useState, useEffect } from "react"

const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

function mclp(v) {
  if (!v && v !== 0) return "—"
  if (Math.abs(v) >= 1e9) return `${(v/1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v/1e6).toFixed(1)}M`
  return v.toLocaleString("es-CL")
}

export default function StockAnalisisModal({ sku, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`/api/forecast/stock-analisis/${sku}`)
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || "Error")))
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [sku])

  const neto = (qty, precio) => Math.round(qty * precio / 1.19)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "#13112a", border: "1px solid #2d2458", borderRadius: 12,
          padding: 28, minWidth: 820, maxWidth: 960, maxHeight: "88vh",
          overflowY: "auto", color: "#c9d1d9",
        }}
      >
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>
              Análisis de Stock — {sku}
            </div>
            {data && (
              <div style={{ fontSize: 12, color: "#8891aa", marginTop: 4 }}>
                {data.descripcion} · Stock actual: <span style={{ color: data.stock_actual > 0 ? "#facc15" : "#ef4444", fontWeight: 700 }}>{data.stock_actual}</span> u · P. Bruto: ${mclp(data.precio_lp)}
              </div>
            )}
          </div>
          <button onClick={onClose} style={{ background:"none",border:"none",color:"#8891aa",cursor:"pointer",fontSize:18 }}>✕</button>
        </div>

        {loading && <div style={{ padding: 40, textAlign:"center", color:"#8891aa" }}>Cargando...</div>}
        {error   && <div style={{ padding: 20, color:"#ef4444" }}>Error: {error}</div>}

        {data && (() => {
          const ma = data.mes_actual - 1  // índice 0-based del mes actual
          const totalPuesto    = data.forecast.reduce((s,v)=>s+v, 0)
          const totalProyectado = data.lo_proyectado.reduce((s,v)=>s+v, 0)
          const netoPuesto     = neto(totalPuesto,     data.precio_lp)
          const netoProyectado = neto(totalProyectado, data.precio_lp)

          return (
            <>
              {/* Tabla mes a mes */}
              <div style={{ overflowX:"auto", marginBottom: 24 }}>
                <table style={{ width:"100%", fontSize: 12, borderCollapse:"collapse" }}>
                  <thead>
                    <tr style={{ background:"#1a1230" }}>
                      <th style={{ padding:"8px 10px", textAlign:"left", color:"#8891aa", borderBottom:"1px solid #2d2458" }}>Concepto</th>
                      {MESES.map((m,i) => (
                        <th key={i} style={{
                          padding:"8px 6px", textAlign:"right", borderBottom:"1px solid #2d2458",
                          color: i === ma ? "#a78bfa" : (i < ma ? "#64748b" : "#8891aa"),
                          fontWeight: i === ma ? 700 : 400,
                        }}>{m}</th>
                      ))}
                      <th style={{ padding:"8px 10px", textAlign:"right", color:"#8891aa", borderBottom:"1px solid #2d2458" }}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Ventas reales */}
                    <tr style={{ background:"#0d1117" }}>
                      <td style={{ padding:"6px 10px", color:"#64748b", fontStyle:"italic" }}>Ventas reales 2026</td>
                      {data.ventas_reales.map((v,i) => (
                        <td key={i} style={{
                          padding:"6px 6px", textAlign:"right", fontFamily:"monospace",
                          color: i <= ma ? "#64748b" : "transparent",
                        }}>{i <= ma ? v : "—"}</td>
                      ))}
                      <td style={{ padding:"6px 10px", textAlign:"right", fontFamily:"monospace", color:"#64748b" }}>
                        {data.ventas_reales.slice(0, ma+1).reduce((s,v)=>s+v,0)}
                      </td>
                    </tr>

                    {/* Llegadas */}
                    {data.llegadas.some(v => v > 0) && (
                      <tr style={{ background:"#0f1320" }}>
                        <td style={{ padding:"6px 10px", color:"#38bdf8" }}>⬆ Llegadas programadas</td>
                        {data.llegadas.map((v,i) => (
                          <td key={i} style={{ padding:"6px 6px", textAlign:"right", fontFamily:"monospace", color: v > 0 ? "#38bdf8" : "#2d2458" }}>
                            {v > 0 ? v : "—"}
                          </td>
                        ))}
                        <td style={{ padding:"6px 10px", textAlign:"right", fontFamily:"monospace", color:"#38bdf8" }}>
                          {data.llegadas.reduce((s,v)=>s+v,0)}
                        </td>
                      </tr>
                    )}

                    {/* Lo Puesto (forecast original) */}
                    <tr style={{ background:"#111827" }}>
                      <td style={{ padding:"8px 10px", color:"#e2e8f0", fontWeight: 600 }}>Lo Puesto (Forecast)</td>
                      {data.forecast.map((v,i) => (
                        <td key={i} style={{
                          padding:"8px 6px", textAlign:"right", fontFamily:"monospace", fontWeight: 600,
                          color: i < ma ? "#374151" : (i === ma ? "#e2e8f0" : "#93c5fd"),
                          background: i === ma ? "#1a1f2e" : "transparent",
                        }}>{v || "—"}</td>
                      ))}
                      <td style={{ padding:"8px 10px", textAlign:"right", fontFamily:"monospace", fontWeight: 700, color:"#93c5fd" }}>
                        {totalPuesto}
                      </td>
                    </tr>

                    {/* Lo Proyectado */}
                    <tr style={{ background:"#0f0d1e" }}>
                      <td style={{ padding:"8px 10px", color:"#a78bfa", fontWeight: 700 }}>Lo Proyectado (stock)</td>
                      {data.lo_proyectado.map((v,i) => (
                        <td key={i} style={{
                          padding:"8px 6px", textAlign:"right", fontFamily:"monospace", fontWeight: 700,
                          color: i < ma ? "#374151" : (v === 0 ? "#ef4444" : "#a78bfa"),
                          background: i === ma ? "#1a1230" : "transparent",
                        }}>{i < ma ? (data.ventas_reales[i] || "—") : (v || <span style={{color:"#ef4444"}}>0</span>)}</td>
                      ))}
                      <td style={{ padding:"8px 10px", textAlign:"right", fontFamily:"monospace", fontWeight: 700, color:"#a78bfa" }}>
                        {totalProyectado}
                      </td>
                    </tr>

                    {/* PxQ Puesto */}
                    <tr style={{ background:"#0a0e1a", borderTop:"1px solid #1e2a3a" }}>
                      <td style={{ padding:"6px 10px", color:"#4b5563", fontSize:11 }}>PxQ Lo Puesto (neto)</td>
                      {data.forecast.map((v,i) => (
                        <td key={i} style={{ padding:"6px 6px", textAlign:"right", fontFamily:"monospace", fontSize:11,
                          color: i < ma ? "transparent" : "#4b5563" }}>
                          {i >= ma ? `$${mclp(neto(v, data.precio_lp))}` : ""}
                        </td>
                      ))}
                      <td style={{ padding:"6px 10px", textAlign:"right", fontFamily:"monospace", fontSize:11, color:"#4b5563" }}>
                        ${mclp(netoPuesto)}
                      </td>
                    </tr>

                    {/* PxQ Proyectado */}
                    <tr style={{ background:"#0a0e1a" }}>
                      <td style={{ padding:"6px 10px", color:"#6d28d9", fontSize:11 }}>PxQ Lo Proyectado (neto)</td>
                      {data.lo_proyectado.map((v,i) => (
                        <td key={i} style={{ padding:"6px 6px", textAlign:"right", fontFamily:"monospace", fontSize:11,
                          color: i < ma ? "transparent" : "#6d28d9" }}>
                          {i >= ma ? `$${mclp(neto(v, data.precio_lp))}` : ""}
                        </td>
                      ))}
                      <td style={{ padding:"6px 10px", textAlign:"right", fontFamily:"monospace", fontSize:11, color:"#6d28d9" }}>
                        ${mclp(netoProyectado)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Resumen y opciones de compra */}
              <div style={{ display:"flex", gap:16, marginBottom:20 }}>
                {/* Resumen totales */}
                <div style={{ flex:1, background:"#1a1230", border:"1px solid #2d2458", borderRadius:10, padding:16 }}>
                  <div style={{ fontSize:13, fontWeight:700, color:"#8891aa", marginBottom:12 }}>Resumen anual</div>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
                    <div>
                      <div style={{ fontSize:11, color:"#64748b" }}>Lo Puesto (unid.)</div>
                      <div style={{ fontSize:20, fontWeight:700, color:"#93c5fd" }}>{totalPuesto.toLocaleString("es-CL")}</div>
                      <div style={{ fontSize:11, color:"#4b5563" }}>Neto: ${mclp(netoPuesto)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize:11, color:"#64748b" }}>Lo Proyectado (unid.)</div>
                      <div style={{ fontSize:20, fontWeight:700, color:"#a78bfa" }}>{totalProyectado.toLocaleString("es-CL")}</div>
                      <div style={{ fontSize:11, color:"#4b5563" }}>Neto: ${mclp(netoProyectado)}</div>
                    </div>
                  </div>
                  {totalProyectado < totalPuesto && (
                    <div style={{ marginTop:10, fontSize:11, color:"#f97316", background:"#1c0a00", borderRadius:6, padding:"6px 10px" }}>
                      ⚠ Brecha: <strong>{(totalPuesto - totalProyectado).toLocaleString("es-CL")} unidades</strong> ({Math.round((1 - totalProyectado/totalPuesto)*100)}%) no cubierta por stock
                    </div>
                  )}
                </div>

                {/* Opciones de compra */}
                <div style={{ flex:1, background:"#0e1a0e", border:"1px solid #166534", borderRadius:10, padding:16 }}>
                  <div style={{ fontSize:13, fontWeight:700, color:"#8891aa", marginBottom:12 }}>Opciones de compra</div>
                  <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
                    <div style={{ background:"#0a1f0a", borderRadius:8, padding:12 }}>
                      <div style={{ fontSize:11, color:"#86efac", marginBottom:4 }}>Opción A — cubrir Lo Puesto (forecast)</div>
                      <div style={{ fontSize:22, fontWeight:700, color:"#4ade80" }}>{data.compra_para_fc.toLocaleString("es-CL")} u</div>
                      <div style={{ fontSize:11, color:"#166534" }}>Inversión estimada: ${mclp(Math.round(data.compra_para_fc * data.precio_lp / 1.19))}</div>
                    </div>
                    <div style={{ background:"#1a0a2e", borderRadius:8, padding:12 }}>
                      <div style={{ fontSize:11, color:"#c4b5fd", marginBottom:4 }}>Opción B — cubrir Lo Proyectado (conservador)</div>
                      <div style={{ fontSize:22, fontWeight:700, color:"#a78bfa" }}>{data.compra_para_proy.toLocaleString("es-CL")} u</div>
                      <div style={{ fontSize:11, color:"#4c1d95" }}>Inversión estimada: ${mclp(Math.round(data.compra_para_proy * data.precio_lp / 1.19))}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Nota marketplace */}
              <div style={{ background:"#1a0c00", border:"1px solid #7c2d12", borderRadius:8, padding:12, fontSize:12, color:"#fb923c" }}>
                <strong>⬡ Impacto MKTP:</strong> Un stockout superior a 7 días reduce la velocidad de venta al reanudar el stock (semana 1-2: ~50%, semana 3-4: ~75%, mes 2: ~100%). Mayor de 30 días: semana 1-2: ~25%, mes 2: ~65%, mes 3+: ~95%. Considerar en la proyección post-reposición.
              </div>
            </>
          )
        })()}
      </div>
    </div>
  )
}
