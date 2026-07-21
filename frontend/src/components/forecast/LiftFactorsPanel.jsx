import { useState, useEffect } from "react"
import { getLiftFactors, crearLiftFactor, actualizarLiftFactor, eliminarLiftFactor } from "../../services/api"

const EMPTY = {
  nombre_evento: "",
  canal: "",
  sku_pattern: "",
  fecha_inicio: "",
  fecha_fin: "",
  multiplicador: 1.0,
  tipo: "manual",
  notas: "",
}

function fmt(d) {
  if (!d) return "—"
  return String(d).slice(0, 10)
}

export default function LiftFactorsPanel() {
  const [lifts,   setLifts]   = useState([])
  const [loading, setLoading] = useState(false)
  const [form,    setForm]    = useState(null)   // null = cerrado, {} = nuevo, {id,...} = editar
  const [msg,     setMsg]     = useState(null)
  const [saving,  setSaving]  = useState(false)

  useEffect(() => { cargar() }, [])

  async function cargar() {
    setLoading(true)
    try {
      const data = await getLiftFactors()
      setLifts(data)
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  function abrirNuevo() { setForm({ ...EMPTY }); setMsg(null) }
  function abrirEditar(lf) {
    setForm({
      id: lf.id,
      nombre_evento: lf.nombre_evento,
      canal: lf.canal || "",
      sku_pattern: lf.sku_pattern || "",
      fecha_inicio: String(lf.fecha_inicio).slice(0, 10),
      fecha_fin:    String(lf.fecha_fin).slice(0, 10),
      multiplicador: lf.multiplicador,
      tipo: lf.tipo,
      notas: lf.notas || "",
    })
    setMsg(null)
  }

  async function guardar() {
    if (!form.nombre_evento || !form.fecha_inicio || !form.fecha_fin || !form.multiplicador) {
      setMsg({ tipo: "error", texto: "Nombre, fechas y multiplicador son obligatorios" })
      return
    }
    setSaving(true)
    setMsg(null)
    try {
      const payload = {
        nombre_evento: form.nombre_evento,
        canal:         form.canal || null,
        sku_pattern:   form.sku_pattern || null,
        fecha_inicio:  form.fecha_inicio,
        fecha_fin:     form.fecha_fin,
        multiplicador: parseFloat(form.multiplicador),
        tipo:          form.tipo,
        notas:         form.notas || null,
      }
      if (form.id) {
        await actualizarLiftFactor(form.id, payload)
        setMsg({ tipo: "ok", texto: "Lift factor actualizado" })
      } else {
        await crearLiftFactor(payload)
        setMsg({ tipo: "ok", texto: "Lift factor creado" })
      }
      setForm(null)
      await cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setSaving(false)
    }
  }

  async function eliminar(id, nombre) {
    if (!window.confirm(`¿Eliminar "${nombre}"?`)) return
    try {
      await eliminarLiftFactor(id)
      setMsg({ tipo: "ok", texto: "Eliminado" })
      await cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0, color: "#e2e8f0", fontSize: 15 }}>Lift Factors</h3>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            Multiplicadores sobre el forecast base por evento o temporada. Aplican a todos los SKUs / canal salvo que se especifique un patrón.
          </p>
        </div>
        <button onClick={abrirNuevo} style={btnPrimStyle}>+ Nuevo</button>
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

      {/* Formulario inline */}
      {form && (
        <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <h4 style={{ margin: "0 0 12px", color: "#94a3b8", fontSize: 13, textTransform: "uppercase", letterSpacing: 1 }}>
            {form.id ? "Editar lift factor" : "Nuevo lift factor"}
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <Field label="Nombre evento *">
              <input value={form.nombre_evento} onChange={e => setForm(f => ({ ...f, nombre_evento: e.target.value }))} style={inputStyle} placeholder="Ej: CyberDay_Nov2026" />
            </Field>
            <Field label="Canal (vacío = todos)">
              <select value={form.canal} onChange={e => setForm(f => ({ ...f, canal: e.target.value }))} style={inputStyle}>
                <option value="">— Todos —</option>
                <option value="Mercado Libre">Mercado Libre</option>
                <option value="Tienda Propia">Tienda Propia</option>
                <option value="Ripley">Ripley</option>
                <option value="Falabella">Falabella</option>
                <option value="Paris">Paris</option>
              </select>
            </Field>
            <Field label="Patrón SKU (vacío = todos)">
              <input value={form.sku_pattern} onChange={e => setForm(f => ({ ...f, sku_pattern: e.target.value }))} style={inputStyle} placeholder="Ej: R376%" />
            </Field>
            <Field label="Fecha inicio *">
              <input type="date" value={form.fecha_inicio} onChange={e => setForm(f => ({ ...f, fecha_inicio: e.target.value }))} style={inputStyle} />
            </Field>
            <Field label="Fecha fin *">
              <input type="date" value={form.fecha_fin} onChange={e => setForm(f => ({ ...f, fecha_fin: e.target.value }))} style={inputStyle} />
            </Field>
            <Field label="Multiplicador *">
              <input type="number" step="0.01" min="0.1" max="10" value={form.multiplicador} onChange={e => setForm(f => ({ ...f, multiplicador: e.target.value }))} style={inputStyle} />
            </Field>
            <Field label="Notas" style={{ gridColumn: "1 / -1" }}>
              <input value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))} style={inputStyle} placeholder="Descripción opcional" />
            </Field>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
            <button onClick={() => setForm(null)} style={btnSecStyle}>Cancelar</button>
            <button onClick={guardar} disabled={saving} style={btnPrimStyle}>
              {saving ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </div>
      )}

      {/* Tabla */}
      {loading ? (
        <div style={{ padding: 24, color: "#64748b", textAlign: "center" }}>Cargando…</div>
      ) : lifts.length === 0 ? (
        <div style={{ padding: 24, color: "#64748b", textAlign: "center" }}>Sin lift factors configurados</div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#0d1520" }}>
              {["Nombre evento", "Canal", "SKU patrón", "Inicio", "Fin", "×Mult", "Tipo", ""].map(h => (
                <th key={h} style={{ padding: "8px 10px", textAlign: "left", color: "#64748b", fontSize: 12, fontWeight: 600, borderBottom: "1px solid #1e2a3a" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lifts.map((lf, i) => {
              const hoy = new Date().toISOString().slice(0, 10)
              const vigente = String(lf.fecha_inicio).slice(0, 10) <= hoy && hoy <= String(lf.fecha_fin).slice(0, 10)
              return (
                <tr key={lf.id} style={{ background: i % 2 === 0 ? "transparent" : "#0a111c" }}>
                  <td style={tdStyle}>
                    <span style={{ fontWeight: 600, color: vigente ? "#22c55e" : "#e2e8f0" }}>{lf.nombre_evento}</span>
                    {vigente && <span style={{ marginLeft: 6, fontSize: 10, background: "#052e16", color: "#4ade80", padding: "1px 6px", borderRadius: 10 }}>VIGENTE</span>}
                  </td>
                  <td style={tdStyle}>{lf.canal || <span style={{ color: "#64748b" }}>todos</span>}</td>
                  <td style={tdStyle}><code style={{ fontSize: 11 }}>{lf.sku_pattern || <span style={{ color: "#64748b" }}>todos</span>}</code></td>
                  <td style={tdStyle}>{fmt(lf.fecha_inicio)}</td>
                  <td style={tdStyle}>{fmt(lf.fecha_fin)}</td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: lf.multiplicador > 1 ? "#f59e0b" : lf.multiplicador < 1 ? "#ef4444" : "#94a3b8" }}>
                      ×{Number(lf.multiplicador).toFixed(2)}
                    </span>
                  </td>
                  <td style={tdStyle}><span style={{ color: "#94a3b8", fontSize: 11 }}>{lf.tipo}</span></td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={() => abrirEditar(lf)} style={{ ...btnSecStyle, padding: "3px 10px", fontSize: 12 }}>Editar</button>
                      <button onClick={() => eliminar(lf.id, lf.nombre_evento)} style={{ background: "#1c0a0a", color: "#f87171", border: "1px solid #7f1d1d", borderRadius: 6, padding: "3px 10px", fontSize: 12, cursor: "pointer" }}>✕</button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: 16, padding: "10px 12px", background: "#0a111c", borderRadius: 6, fontSize: 12, color: "#64748b", lineHeight: 1.7 }}>
        <strong style={{ color: "#94a3b8" }}>Cómo funcionan los lift factors:</strong><br/>
        El motor Holt-Winters genera un forecast base (Capa 1). Los lift factors multiplican ese valor para el período que cae entre las fechas configuradas (Capa 2).
        Si el mismo período tiene varios lift factors aplicables, se multiplican entre sí.
        Ej: CyberDay ×1.8 + Despacho gratis ×1.1 → forecast final ×1.98.
      </div>
    </div>
  )
}

function Field({ label, children, style }) {
  return (
    <div style={style}>
      <label style={{ display: "block", fontSize: 11, color: "#64748b", marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  )
}

const tdStyle = { padding: "8px 10px", fontSize: 13, borderBottom: "1px solid #0f1a28" }
const inputStyle = { width: "100%", background: "#060d14", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "6px 10px", fontSize: 13, boxSizing: "border-box" }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }
const btnSecStyle = { background: "#1e2a3a", color: "#94a3b8", border: "1px solid #2a3a4a", borderRadius: 6, padding: "5px 12px", fontSize: 13, cursor: "pointer" }
