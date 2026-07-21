import { useState, useEffect } from "react"
import { getOverrides, crearOverride, eliminarOverride } from "../../services/api"

const EMPTY = { sku: "", canal: "", periodo: "", valor_override: "", motivo: "" }

function fmt(n) { return n != null ? Number(n).toLocaleString("es-CL") : "—" }
function fmtDate(d) { return d ? String(d).slice(0, 10) : "—" }

const PERIODOS = (() => {
  const meses = []
  const hoy = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(hoy.getFullYear(), hoy.getMonth() + i, 1)
    meses.push({ value: d.toISOString().slice(0, 10), label: d.toLocaleDateString("es-CL", { month: "short", year: "numeric" }) })
  }
  return meses
})()

export default function OverridePanel() {
  const [overrides, setOverrides] = useState([])
  const [loading,   setLoading]   = useState(false)
  const [form,      setForm]      = useState(null)
  const [msg,       setMsg]       = useState(null)
  const [saving,    setSaving]    = useState(false)

  useEffect(() => { cargar() }, [])

  async function cargar() {
    setLoading(true)
    try {
      const data = await getOverrides()
      setOverrides(data)
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  async function guardar() {
    if (!form.sku || !form.canal || !form.periodo || !form.valor_override || !form.motivo) {
      setMsg({ tipo: "error", texto: "Todos los campos son obligatorios" })
      return
    }
    setSaving(true)
    setMsg(null)
    try {
      const res = await crearOverride({
        sku: form.sku.trim().toUpperCase(),
        canal: form.canal,
        periodo: form.periodo,
        valor_override: parseFloat(form.valor_override),
        motivo: form.motivo,
      })
      setMsg({ tipo: "ok", texto: `Override aplicado: ${fmt(res.valor_original)} → ${fmt(res.valor_override)} uds` })
      setForm(null)
      await cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    } finally {
      setSaving(false)
    }
  }

  async function eliminar(id, sku) {
    if (!window.confirm(`¿Eliminar override de "${sku}" y restaurar valor HW?`)) return
    try {
      const res = await eliminarOverride(id)
      setMsg({ tipo: "ok", texto: `Override eliminado — restaurado a ${fmt(res.restaurado)} uds` })
      await cargar()
    } catch (e) {
      setMsg({ tipo: "error", texto: e.message })
    }
  }

  return (
    <div style={{ padding: 16, maxWidth: 900 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0, color: "#e2e8f0", fontSize: 15 }}>Overrides Manuales</h3>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            Sobreescribe el forecast_final para un SKU/canal/período específico. El motor HW queda como valor de referencia.
          </p>
        </div>
        <button onClick={() => { setForm({ ...EMPTY }); setMsg(null) }} style={btnPrimStyle}>+ Nuevo override</button>
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

      {/* Formulario */}
      {form && (
        <div style={{ background: "#0d1520", border: "1px solid #1e2a3a", borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <h4 style={{ margin: "0 0 12px", color: "#94a3b8", fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>
            Nuevo override
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <Field label="SKU *">
              <input value={form.sku} onChange={e => setForm(f => ({ ...f, sku: e.target.value }))}
                style={inputStyle} placeholder="Ej: R3765" />
            </Field>
            <Field label="Canal *">
              <select value={form.canal} onChange={e => setForm(f => ({ ...f, canal: e.target.value }))} style={inputStyle}>
                <option value="">— Seleccionar —</option>
                <option value="Mercado Libre">Mercado Libre</option>
                <option value="Tienda Propia">Tienda Propia</option>
                <option value="Ripley">Ripley</option>
                <option value="Falabella">Falabella</option>
                <option value="Paris">Paris</option>
              </select>
            </Field>
            <Field label="Período *">
              <select value={form.periodo} onChange={e => setForm(f => ({ ...f, periodo: e.target.value }))} style={inputStyle}>
                <option value="">— Seleccionar —</option>
                {PERIODOS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </Field>
            <Field label="Forecast override (uds) *">
              <input type="number" min="0" step="1" value={form.valor_override}
                onChange={e => setForm(f => ({ ...f, valor_override: e.target.value }))}
                style={inputStyle} placeholder="Ej: 250" />
            </Field>
            <Field label="Motivo *" style={{ gridColumn: "2 / -1" }}>
              <input value={form.motivo}
                onChange={e => setForm(f => ({ ...f, motivo: e.target.value }))}
                style={inputStyle} placeholder="Ej: Promo flash julio + acuerdo canal — subida estimada 40%" />
            </Field>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
            <button onClick={() => setForm(null)} style={btnSecStyle}>Cancelar</button>
            <button onClick={guardar} disabled={saving} style={btnPrimStyle}>
              {saving ? "Aplicando…" : "Aplicar override"}
            </button>
          </div>
        </div>
      )}

      {/* Tabla */}
      {loading ? (
        <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>Cargando…</div>
      ) : overrides.length === 0 ? (
        <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>
          Sin overrides activos. El forecast proviene 100% del motor Holt-Winters.
        </div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#0d1520" }}>
              {["SKU", "Canal", "Período", "HW original", "Override", "Δ", "Motivo", ""].map(h => (
                <th key={h} style={{ padding: "8px 10px", textAlign: h === "HW original" || h === "Override" || h === "Δ" ? "right" : "left", color: "#64748b", fontSize: 12, fontWeight: 600, borderBottom: "1px solid #1e2a3a" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {overrides.map((ov, i) => {
              const delta = ov.valor_override - ov.valor_original
              const deltaPct = ov.valor_original > 0 ? (delta / ov.valor_original) * 100 : null
              return (
                <tr key={ov.id} style={{ background: i % 2 === 0 ? "transparent" : "#0a111c" }}>
                  <td style={tdStyle}><code style={{ fontSize: 11 }}>{ov.sku}</code></td>
                  <td style={tdStyle}>{ov.canal}</td>
                  <td style={tdStyle}>{fmtDate(ov.periodo).slice(0, 7)}</td>
                  <td style={{ ...tdStyle, textAlign: "right", color: "#64748b" }}>{fmt(Math.round(ov.valor_original))}</td>
                  <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700 }}>{fmt(Math.round(ov.valor_override))}</td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <span style={{ color: delta > 0 ? "#4ade80" : delta < 0 ? "#f87171" : "#94a3b8" }}>
                      {delta > 0 ? "+" : ""}{fmt(Math.round(delta))}
                      {deltaPct != null && <span style={{ fontSize: 11, marginLeft: 4 }}>({deltaPct > 0 ? "+" : ""}{deltaPct.toFixed(0)}%)</span>}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#94a3b8" }}>{ov.motivo}</td>
                  <td style={tdStyle}>
                    <button
                      onClick={() => eliminar(ov.id, ov.sku)}
                      style={{ background: "#1c0a0a", color: "#f87171", border: "1px solid #7f1d1d", borderRadius: 6, padding: "3px 10px", fontSize: 12, cursor: "pointer" }}
                    >
                      ✕ Revertir
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: 16, padding: "10px 12px", background: "#0a111c", borderRadius: 6, fontSize: 12, color: "#64748b", lineHeight: 1.7 }}>
        <strong style={{ color: "#94a3b8" }}>Nota:</strong> El override reemplaza el <code>forecast_final</code> en la tabla y en la vista materializada.
        El forecast HW (base) queda guardado en <code>valor_original</code>. Al revertir se restaura el valor del motor.
        Los overrides aparecen marcados con <code>es_override=true</code> en el CSV de exportación.
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

const tdStyle      = { padding: "8px 10px", fontSize: 13, borderBottom: "1px solid #0f1a28", whiteSpace: "nowrap" }
const inputStyle   = { width: "100%", background: "#060d14", border: "1px solid #1e2a3a", color: "#e2e8f0", borderRadius: 6, padding: "6px 10px", fontSize: 13, boxSizing: "border-box" }
const btnPrimStyle = { background: "#3d7eff", color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }
const btnSecStyle  = { background: "#1e2a3a", color: "#94a3b8", border: "1px solid #2a3a4a", borderRadius: 6, padding: "5px 12px", fontSize: 13, cursor: "pointer" }
