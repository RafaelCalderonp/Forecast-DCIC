import { useState, useEffect } from "react"
import { calcularNeto, redondearBruto, formatCLP } from "../../utils/precios"

export default function ProductoForm({ producto, temporadas, onGuardar, onCerrar }) {
  const [form, setForm] = useState({
    sku: "", marca_id: "", categoria_id: "", temporada_id: "",
    descripcion: "", precio_venta_bruto: "", precio_venta_neto: "",
  })
  const [marcaNombre, setMarcaNombre] = useState("")
  const [categoriaNombre, setCategoriaNombre] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (producto) {
      setForm({
        sku: producto.sku,
        marca_id: producto.marca_id || "",
        categoria_id: producto.categoria_id || "",
        temporada_id: producto.temporada_id || "",
        descripcion: producto.descripcion || "",
        precio_venta_bruto: producto.precio_venta_bruto || "",
        precio_venta_neto: producto.precio_venta_neto || "",
      })
      setMarcaNombre(producto.marca?.nombre || "")
      setCategoriaNombre(producto.categoria?.nombre || "")
    }
  }, [producto])

  const handleBruto = (val) => {
    const bruto = val
    const neto = calcularNeto(val)
    setForm(f => ({ ...f, precio_venta_bruto: bruto, precio_venta_neto: neto }))
  }

  const handleBrutoBlur = () => {
    if (form.precio_venta_bruto) {
      const redondeado = redondearBruto(form.precio_venta_bruto)
      const neto = calcularNeto(redondeado)
      setForm(f => ({ ...f, precio_venta_bruto: redondeado, precio_venta_neto: neto }))
    }
  }

  const handleSubmit = async () => {
    setError("")
    if (!form.sku || !marcaNombre || !categoriaNombre || !form.precio_venta_bruto) {
      setError("SKU, Marca, Categoría y Precio Bruto son obligatorios")
      return
    }
    setLoading(true)
    try {
      // Enviamos nombres de marca y categoría — el backend los crea si no existen
      await onGuardar({
        sku: form.sku.trim().toUpperCase(),
        marca_nombre: marcaNombre.trim(),
        categoria_nombre: categoriaNombre.trim(),
        temporada_id: form.temporada_id || null,
        descripcion: form.descripcion || null,
        precio_venta_bruto: redondearBruto(form.precio_venta_bruto),
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const esEdicion = !!producto

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onCerrar()}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">{esEdicion ? "Editar Producto" : "Nuevo Producto"}</span>
          <button className="modal-close" onClick={onCerrar}>✕</button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">SKU *</label>
            <input
              className="form-input" placeholder="Ej: R3357"
              value={form.sku}
              onChange={e => setForm(f => ({ ...f, sku: e.target.value }))}
              disabled={esEdicion}
              style={esEdicion ? { opacity: 0.6 } : {}}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Temporada</label>
            <select className="form-select" value={form.temporada_id} onChange={e => setForm(f => ({ ...f, temporada_id: e.target.value }))}>
              <option value="">— Sin temporada —</option>
              {temporadas.map(t => <option key={t.id} value={t.id}>{t.nombre}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Marca *</label>
            <input
              className="form-input" placeholder="Ej: Acqui"
              value={marcaNombre}
              onChange={e => setMarcaNombre(e.target.value)}
            />
            <span className="form-hint">Si no existe, se crea automáticamente</span>
          </div>

          <div className="form-group">
            <label className="form-label">Categoría *</label>
            <input
              className="form-input" placeholder="Ej: Calefacción"
              value={categoriaNombre}
              onChange={e => setCategoriaNombre(e.target.value)}
            />
            <span className="form-hint">Si no existe, se crea automáticamente</span>
          </div>

          <div className="form-group full">
            <label className="form-label">Descripción</label>
            <input
              className="form-input" placeholder="Descripción del producto"
              value={form.descripcion}
              onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Precio Venta Bruto (CLP) *</label>
            <input
              className="form-input" type="number" placeholder="0.00" step="0.01" min="0"
              value={form.precio_venta_bruto}
              onChange={e => handleBruto(e.target.value)}
              onBlur={handleBrutoBlur}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Precio Venta Neto (calculado)</label>
            <div className="price-display">
              {form.precio_venta_neto ? formatCLP(form.precio_venta_neto) : "—"}
            </div>
            <span className="form-hint">= Bruto ÷ 1,19 · redondeado a 2 decimales</span>
          </div>
        </div>

        <div className="form-actions" style={{ marginTop: 24 }}>
          <button className="btn btn-secondary" onClick={onCerrar}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? <span className="spinner"/> : null}
            {esEdicion ? "Guardar cambios" : "Crear producto"}
          </button>
        </div>
      </div>
    </div>
  )
}
