import { useState, useEffect, useCallback } from "react"
import { getProductos, getTemporadas, crearProducto, actualizarProducto, eliminarProducto } from "../../services/api"
import { useAuth } from "../../context/AuthContext"
import { formatCLP, calcularNeto } from "../../utils/precios"
import ProductoForm from "./ProductoForm"
import CargaMasiva from "./CargaMasiva"

const COMENTARIOS_BASE = ['Descontinuar', 'Nuevo', 'Calidad']
const LS_KEY = 'dcic_comentarios_extra'
const COMENTARIO_STYLE = {
  'Descontinuar': { bg: '#fee2e2', color: '#991b1b' },
  'Nuevo':        { bg: '#d1fae5', color: '#065f46' },
  'Calidad':      { bg: '#eff6ff', color: '#1e40af' },
}

export default function ProductosPage() {
  const { authFetch } = useAuth()
  const [tab, setTab]               = useState("lista")
  const [productos, setProductos]   = useState([])
  const [temporadas, setTemporadas] = useState([])
  const [busqueda, setBusqueda]     = useState("")
  const [sortBy, setSortBy]         = useState("marca")
  const [sortDir, setSortDir]       = useState("asc")
  const [loading, setLoading]       = useState(true)
  const [modalProducto, setModalProducto] = useState(null)  // null=cerrado, {}=nuevo, obj=editar
  const [confirmarEliminar, setConfirmarEliminar] = useState(null)
  const [mensaje, setMensaje]       = useState(null)
  const [filtroCard, setFiltroCard] = useState(null)
  const [modalForecast, setModalForecast] = useState(null) // { sku } cuando está abierto
  const [filtroComentario, setFiltroComentario] = useState('')
  const [multiTerminos, setMultiTerminos] = useState([]) // cuando se pegan múltiples valores
  const [comentariosExtra, setComentariosExtra] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || '[]') } catch { return [] }
  })

  const cargarDatos = useCallback(async () => {
    setLoading(true)
    try {
      const [prods, temps] = await Promise.all([getProductos(), getTemporadas()])
      setProductos(prods)
      setTemporadas(temps)
    } catch (e) {
      mostrarMensaje("error", e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { cargarDatos() }, [cargarDatos])

  const mostrarMensaje = (tipo, texto) => {
    setMensaje({ tipo, texto })
    setTimeout(() => setMensaje(null), 4000)
  }

  async function generarHoltWinters(sku, desdeMes, desdeAnio) {
    mostrarMensaje('success', `Generando forecast para ${sku}…`)
    setModalForecast(null)
    try {
      const res = await authFetch(
        `/api/forecast/generar-holt-winters/${sku}?desde_mes=${desdeMes}&desde_anio=${desdeAnio}&hasta_mes=12&hasta_anio=${desdeAnio}`,
        { method: 'POST' }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || err.detalle || `HTTP ${res.status}`)
      }
      const data = await res.json()
      mostrarMensaje('success', `Forecast generado (${data.metodo}, ${data.meses_generados} meses)`)
    } catch (e) {
      mostrarMensaje('error', `Error generando forecast ${sku}: ${e.message}`)
    }
  }

  async function patchProducto(sku, campos) {
    try {
      const res = await authFetch(`/api/productos/${sku}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(campos),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || err.detalle || err.message || `HTTP ${res.status}`)
      }
      setProductos(prev => prev.map(p => p.sku === sku ? { ...p, ...campos } : p))
    } catch (e) {
      mostrarMensaje('error', `Error al actualizar ${sku}: ${e.message}`)
    }
  }

  const handleGuardar = async (data) => {
    const esEdicion = !!modalProducto?.sku
    if (esEdicion) {
      await actualizarProducto(modalProducto.sku, data)
      mostrarMensaje("success", `Producto ${modalProducto.sku} actualizado`)
    } else {
      await crearProducto(data)
      mostrarMensaje("success", `Producto ${data.sku} creado exitosamente`)
    }
    setModalProducto(null)
    cargarDatos()
  }

  const handleEliminar = async (sku) => {
    try {
      await eliminarProducto(sku)
      mostrarMensaje("success", `Producto ${sku} eliminado`)
      setConfirmarEliminar(null)
      cargarDatos()
    } catch (e) {
      mostrarMensaje("error", e.message)
    }
  }

  const filtrados = productos
    .filter(p => {
      if (filtroCard === 'activos')      return p.activo && p.comentario !== 'Descontinuar'
      if (filtroCard === 'inactivos')    return !p.activo
      if (filtroCard === 'discontinuar') return p.comentario === 'Descontinuar'
      if (filtroCard === 'nuevo')        return p.comentario === 'Nuevo'
      if (filtroCard === 'ver_comportamiento') return p.comentario === 'Ver Comportamiento'
      if (filtroCard === 'completar')    return p.marca?.nombre === 'Sin Marca' || p.categoria?.nombre === 'Sin Categoria'
      return true
    })
    .filter(p => {
      if (!filtroComentario) return true
      if (filtroComentario === '__sin__') return !p.comentario
      return p.comentario === filtroComentario
    })
    .filter(p => {
      if (multiTerminos.length > 0) {
        return multiTerminos.some(t =>
          p.sku.toLowerCase() === t ||
          p.sku.toLowerCase().includes(t) ||
          (p.descripcion || "").toLowerCase().includes(t) ||
          (p.marca?.nombre || "").toLowerCase().includes(t) ||
          (p.categoria?.nombre || "").toLowerCase().includes(t)
        )
      }
      const q = busqueda.toLowerCase()
      return !q || (
        p.sku.toLowerCase().includes(q) ||
        (p.descripcion || "").toLowerCase().includes(q) ||
        (p.marca?.nombre || "").toLowerCase().includes(q) ||
        (p.categoria?.nombre || "").toLowerCase().includes(q)
      )
    })
    .sort((a, b) => {
      // Inactivos siempre al fondo, sea cual sea el orden
      if (a.activo !== b.activo) return a.activo ? -1 : 1
      const dir = sortDir === "asc" ? 1 : -1
      let va, vb
      if (sortBy === "marca")       { va = a.marca?.nombre || ""; vb = b.marca?.nombre || "" }
      else if (sortBy === "sku")    { va = a.sku;                 vb = b.sku }
      else if (sortBy === "descripcion") { va = a.descripcion || ""; vb = b.descripcion || "" }
      else if (sortBy === "categoria")     { va = a.categoria?.nombre || ""; vb = b.categoria?.nombre || "" }
      else if (sortBy === "tipo_producto") { va = a.tipo_producto || ""; vb = b.tipo_producto || "" }
      else                          { va = a.marca?.nombre || ""; vb = b.marca?.nombre || "" }
      return va.localeCompare(vb, "es") * dir
    })

  const temporadaNombre = (id) => temporadas.find(t => t.id === id)?.nombre || "—"

  async function exportarProductos(lista, nombre) {
    const XLSX = await import("xlsx")
    const rows = lista.map(p => ({
      'SKU':              p.sku,
      'Marca':            p.marca?.nombre || '',
      'Descripción':      p.descripcion || '',
      'Cat. Principal':   p.categoria?.nombre || '',
      'Subcategoría':     p.subcategoria?.nombre || '',
      'Tipo de Producto': p.tipo_producto || '',
      'Temporada':        p.temporada?.nombre || '',
      'Precio Bruto':     p.precio_venta_bruto || 0,
      'Precio Neto':      Math.round((p.precio_venta_bruto || 0) / 1.19),
      'Stock Total':      p.stock_total ?? 0,
      'Activo':           p.activo ? 'Sí' : 'No',
      'Comentario':       p.comentario || '',
    }))
    const ws = XLSX.utils.json_to_sheet(rows)
    ws['!cols'] = [12,14,40,18,14,14,14,12,10,12,8,16].map(w => ({ wch: w }))
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, nombre)
    XLSX.writeFile(wb, `productos_${nombre.toLowerCase().replace(/ /g,'_')}.xlsx`)
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Productos</div>
          <div className="page-subtitle">{productos.length} productos registrados</div>
        </div>
        <div className="header-actions">
          <button className="btn btn-secondary"
            onClick={() => exportarProductos(filtrados, filtroCard ? ({ activos:'Activos', inactivos:'Inactivos', discontinuar:'Por Discontinuar', nuevo:'Nuevo', ver_comportamiento:'Ver Comportamiento', completar:'Por Completar' })[filtroCard] || 'Filtrados' : 'Filtrados')}
            title={`Exportar ${filtrados.length} productos (vista actual)`}>
            ↓ Excel ({filtrados.length})
          </button>
          <button className="btn btn-secondary"
            onClick={() => exportarProductos(productos, 'Todos')}
            title={`Exportar todos los ${productos.length} productos`}>
            ↓ Excel (Todos)
          </button>
          <button className="btn btn-primary" onClick={() => { setModalProducto({}); setTab("lista") }}>
            + Nuevo producto
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${tab === "lista" ? "active" : ""}`} onClick={() => setTab("lista")}>
          Lista de productos
        </button>
        <button className={`tab ${tab === "masiva" ? "active" : ""}`} onClick={() => setTab("masiva")}>
          Carga masiva Excel
        </button>
      </div>

      <div className="page-body">

        {/* Mensaje global */}
        {mensaje && (
          <div className={`alert alert-${mensaje.tipo === "success" ? "success" : "error"}`}>
            {mensaje.texto}
          </div>
        )}

        {/* LISTA */}
        {tab === "lista" && (
          <>
            {/* Stats */}
            <div className="stats-row">
              <div className="stat-card" style={{ cursor:'pointer', outline: filtroCard === null ? '2px solid #3b82f6' : 'none' }}
                onClick={() => setFiltroCard(null)}>
                <div className="stat-value">{productos.length}</div>
                <div className="stat-label">Total productos</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{[...new Set(productos.map(p => p.marca?.nombre))].filter(Boolean).length}</div>
                <div className="stat-label">Marcas</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{[...new Set(productos.map(p => p.categoria?.nombre))].filter(Boolean).length}</div>
                <div className="stat-label">Categorías</div>
              </div>
              <div className="stat-card" style={{ cursor:'pointer', outline: filtroCard === 'activos' ? '2px solid #22c55e' : 'none' }}
                onClick={() => setFiltroCard(f => f === 'activos' ? null : 'activos')}>
                <div className="stat-value">{productos.filter(p => p.activo && p.comentario !== 'Descontinuar').length}</div>
                <div className="stat-label">Activos</div>
              </div>
              <div className="stat-card" style={{ borderColor: '#64748b', cursor:'pointer', outline: filtroCard === 'inactivos' ? '2px solid #64748b' : 'none' }}
                onClick={() => setFiltroCard(f => f === 'inactivos' ? null : 'inactivos')}>
                <div className="stat-value" style={{ color: '#64748b' }}>{productos.filter(p => !p.activo).length}</div>
                <div className="stat-label">Inactivos</div>
              </div>
              <div className="stat-card" style={{ borderColor: '#f59e0b', cursor:'pointer', outline: filtroCard === 'discontinuar' ? '2px solid #f59e0b' : 'none' }}
                onClick={() => setFiltroCard(f => f === 'discontinuar' ? null : 'discontinuar')}>
                <div className="stat-value" style={{ color: '#f59e0b' }}>{productos.filter(p => p.comentario === 'Descontinuar').length}</div>
                <div className="stat-label">Por discontinuar</div>
              </div>
              <div className="stat-card" style={{ borderColor: '#10b981', cursor:'pointer', outline: filtroCard === 'nuevo' ? '2px solid #10b981' : 'none' }}
                onClick={() => setFiltroCard(f => f === 'nuevo' ? null : 'nuevo')}>
                <div className="stat-value" style={{ color: '#10b981' }}>{productos.filter(p => p.comentario === 'Nuevo').length}</div>
                <div className="stat-label">Nuevo</div>
              </div>
              {productos.filter(p => p.comentario === 'Ver Comportamiento').length > 0 && (
                <div className="stat-card" style={{ borderColor: '#6366f1', cursor:'pointer', outline: filtroCard === 'ver_comportamiento' ? '2px solid #6366f1' : 'none' }}
                  onClick={() => setFiltroCard(f => f === 'ver_comportamiento' ? null : 'ver_comportamiento')}>
                  <div className="stat-value" style={{ color: '#6366f1' }}>{productos.filter(p => p.comentario === 'Ver Comportamiento').length}</div>
                  <div className="stat-label">Ver Comportamiento</div>
                </div>
              )}
              {productos.filter(p => p.marca?.nombre === 'Sin Marca' || p.categoria?.nombre === 'Sin Categoria').length > 0 && (
                <div className="stat-card" style={{ borderColor: '#ef4444', cursor:'pointer', outline: filtroCard === 'completar' ? '2px solid #ef4444' : 'none' }}
                  onClick={() => setFiltroCard(f => f === 'completar' ? null : 'completar')}>
                  <div className="stat-value" style={{ color: '#ef4444' }}>
                    {productos.filter(p => p.marca?.nombre === 'Sin Marca' || p.categoria?.nombre === 'Sin Categoria').length}
                  </div>
                  <div className="stat-label">Por completar</div>
                </div>
              )}
            </div>

            {/* Búsqueda */}
            <div className="search-bar" style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <input
                  className="search-input"
                  placeholder="Buscar por SKU, descripción, marca o categoría… (pega varias celdas de Excel para filtro múltiple)"
                  value={busqueda}
                  onChange={e => {
                    setBusqueda(e.target.value)
                    setMultiTerminos([])
                  }}
                  onPaste={e => {
                    const texto = e.clipboardData.getData('text')
                    const terminos = texto
                      .split(/[\n\r\t,;]+/)
                      .map(t => t.trim().toLowerCase())
                      .filter(Boolean)
                    if (terminos.length > 1) {
                      e.preventDefault()
                      setMultiTerminos(terminos)
                      setBusqueda(terminos.join(', '))
                    }
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Escape' || (e.key === 'Backspace' && multiTerminos.length > 0)) {
                      setBusqueda(''); setMultiTerminos([])
                    }
                  }}
                  style={{ width: '100%' }}
                />
                {multiTerminos.length > 1 && (
                  <div style={{
                    position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                    background: 'var(--accent)', color: '#fff', borderRadius: 12,
                    fontSize: 11, fontWeight: 700, padding: '2px 8px', pointerEvents: 'none',
                  }}>
                    {multiTerminos.length} términos
                  </div>
                )}
              </div>
              <select
                value={filtroComentario}
                onChange={e => setFiltroComentario(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #2a3a50', background: '#0d1520', color: '#e2e8f0', fontSize: 13, minWidth: 180 }}
              >
                <option value="">Todos los comentarios</option>
                <option value="__sin__">Sin comentario</option>
                {[...new Set([...COMENTARIOS_BASE, ...comentariosExtra, ...productos.map(p => p.comentario).filter(Boolean)])].sort().map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Tabla */}
            <div className="card" style={{ padding: 0 }}>
              {loading ? (
                <div style={{ padding: 40, textAlign: "center" }}><span className="spinner"/></div>
              ) : filtrados.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">⊡</div>
                  <div>{busqueda ? "Sin resultados para esa búsqueda" : "No hay productos. Crea el primero."}</div>
                </div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {[
                          { key: "marca",         label: "Marca"             },
                          { key: "sku",           label: "SKU"               },
                          { key: "descripcion",   label: "Descripción"       },
                          { key: "categoria",     label: "Subcategoría"      },
                          { key: "tipo_producto", label: "Tipo de Producto"  },
                        ].map(col => (
                          <th key={col.key} style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap", padding: "6px 4px" }}
                            onClick={() => {
                              if (sortBy === col.key) setSortDir(d => d === "asc" ? "desc" : "asc")
                              else { setSortBy(col.key); setSortDir("asc") }
                            }}>
                            {col.label}
                            {sortBy === col.key ? (sortDir === "asc" ? " ↑" : " ↓") : " ↕"}
                          </th>
                        ))}
                        <th style={{padding:"6px 4px"}}>Temporada</th>
                        <th style={{ textAlign: "right" }}>P. Bruto</th>
                        <th style={{ textAlign: "right" }}>P. Neto</th>
                        <th style={{ textAlign: "right" }}>Stock Total</th>
                        <th style={{ textAlign: "center" }}>Activo</th>
                        <th>Comentario</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtrados.map(p => (
                        <tr key={p.sku}>
                          <td style={{padding:"4px 4px"}}><span className="badge badge-blue">{p.marca?.nombre || "—"}</span></td>
                          <td style={{padding:"4px 4px"}}><span className="td-mono">{p.sku}</span></td>
                          <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding:"4px 4px" }}>
                            {p.descripcion || <span style={{ color: "var(--text3)" }}>—</span>}
                          </td>
                          <td style={{padding:"4px 4px"}}><span className="badge badge-gray" title={p.categoria?.nombre}>{p.subcategoria?.nombre || p.categoria?.nombre || "—"}</span></td>
                          <td style={{ fontSize: 11, color: p.tipo_producto ? "var(--text2)" : "#ef4444", padding:"4px 4px" }}
                              title={p.tipo_producto || "Sin clasificar"}>
                            {p.tipo_producto || <em style={{opacity:0.5}}>—</em>}
                          </td>
                          <td style={{ fontSize: 11, color: "var(--text2)", padding:"4px 4px" }}>{p.temporada?.nombre || "—"}</td>
                          <td className="td-price">{formatCLP(p.precio_venta_bruto)}</td>
                          <td className="td-price" style={{ color: "var(--accent2)" }}>{formatCLP(calcularNeto(p.precio_venta_bruto))}</td>
                          <td style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 13, paddingRight: 16,
                            color: p.stock_total === 0 ? "#ef4444" : "var(--text)" }}>
                            {p.stock_total ?? 0}
                          </td>
                          {/* Switch Activo/Inactivo */}
                          <td style={{ textAlign: "center" }}>
                            <label style={{ display: "inline-flex", alignItems: "center", cursor: "pointer", gap: 6 }}>
                              <div
                                onClick={() => {
  if (p.activo) {
    patchProducto(p.sku, { activo: false, comentario: null })
  } else {
    setModalForecast({ sku: p.sku, activar: true })
  }
}}
                                style={{
                                  width: 36, height: 20, borderRadius: 10, cursor: "pointer",
                                  background: p.activo ? "#16a34a" : "#94a3b8",
                                  position: "relative", transition: "background .2s",
                                  flexShrink: 0,
                                }}>
                                <div style={{
                                  position: "absolute", top: 2, left: p.activo ? 18 : 2,
                                  width: 16, height: 16, borderRadius: "50%",
                                  background: "#fff", transition: "left .2s",
                                  boxShadow: "0 1px 3px rgba(0,0,0,.3)",
                                }} />
                              </div>
                              <span style={{ fontSize: 11, color: p.activo ? "#16a34a" : "#94a3b8", fontWeight: 600 }}>
                                {p.activo ? "Activo" : "Inactivo"}
                              </span>
                            </label>
                          </td>
                          {/* Comentario libre con sugerencias */}
                          <td>
                            <input
                              list={`cmt-${p.sku}`}
                              defaultValue={p.comentario || ''}
                              placeholder="— sin comentario —"
                              onBlur={e => {
                                const val = e.target.value.trim() || null
                                if (val !== (p.comentario || null))
                                  patchProducto(p.sku, { comentario: val })
                                // Si es nuevo comentario → agregar a predefinidos
                                if (val && !COMENTARIOS_BASE.includes(val) && !comentariosExtra.includes(val)) {
                                  const nuevos = [...comentariosExtra, val]
                                  setComentariosExtra(nuevos)
                                  localStorage.setItem(LS_KEY, JSON.stringify(nuevos))
                                }
                              }}
                              onKeyDown={e => { if (e.key === 'Enter') e.target.blur() }}
                              style={{
                                fontSize: 11, padding: "3px 8px", borderRadius: 12,
                                border: p.comentario ? "1px solid " + (COMENTARIO_STYLE[p.comentario]?.color || '#6366f1') : "1px solid #2d3748",
                                fontWeight: p.comentario ? 600 : 400,
                                background: COMENTARIO_STYLE[p.comentario]?.bg || "transparent",
                                color: COMENTARIO_STYLE[p.comentario]?.color || "#94a3b8",
                                width: 130, outline: "none",
                              }}
                            />
                            <datalist id={`cmt-${p.sku}`}>
                              {[...COMENTARIOS_BASE, ...comentariosExtra].map(c => <option key={c} value={c}/>)}
                            </datalist>
                          </td>
                          <td>
                            <div className="td-actions">
                              {p.activo && (
                                <button
                                  className="btn btn-sm"
                                  title="Generar forecast automático con Holt-Winters"
                                  onClick={() => setModalForecast({ sku: p.sku })}
                                  style={{ background: '#1e3a5f', color: '#60a5fa', border: '1px solid #2d5a9e', fontSize: 11 }}
                                >
                                  📈 Forecast
                                </button>
                              )}
                              <button className="btn btn-sm btn-secondary" onClick={() => setModalProducto(p)}>Editar</button>
                              <button className="btn btn-sm btn-danger" onClick={() => setConfirmarEliminar(p.sku)}>✕</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* CARGA MASIVA */}
        {tab === "masiva" && (
          <CargaMasiva onExito={() => { cargarDatos(); mostrarMensaje("success", "Productos cargados correctamente") }} />
        )}
      </div>

      {/* Modal nuevo/editar */}
      {modalProducto !== null && (
        <ProductoForm
          producto={modalProducto?.sku ? modalProducto : null}
          temporadas={temporadas}
          onGuardar={handleGuardar}
          onCerrar={() => setModalProducto(null)}
        />
      )}

      {/* Modal confirmar eliminar */}
      {modalForecast && (() => {
        const hoy = new Date()
        const esActivacion = !!modalForecast.activar
        const confirmar = async (conForecast) => {
          if (esActivacion) await patchProducto(modalForecast.sku, { activo: true })
          if (conForecast) {
            const mes  = parseInt(document.getElementById('hw-mes').value)
            const anio = parseInt(document.getElementById('hw-anio').value)
            await generarHoltWinters(modalForecast.sku, mes, anio)
          } else {
            setModalForecast(null)
          }
        }
        return (
          <div className="modal-overlay" onClick={() => setModalForecast(null)}>
            <div className="modal" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <span className="modal-title">
                  {esActivacion ? `Activar producto — ${modalForecast.sku}` : `Generar Forecast — ${modalForecast.sku}`}
                </span>
                <button className="modal-close" onClick={() => setModalForecast(null)}>✕</button>
              </div>
              {esActivacion && (
                <p style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 16 }}>
                  El producto será activado. ¿Deseas generar el forecast automático con <strong>Holt-Winters</strong> desde el mes indicado?
                </p>
              )}
              {!esActivacion && (
                <p style={{ color: 'var(--text2)', fontSize: 13, marginBottom: 16 }}>
                  Se aplicará <strong>Holt-Winters</strong> sobre el historial de ventas y se generará el forecast desde el mes elegido hasta diciembre.
                </p>
              )}
              <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 4 }}>Mes inicio</label>
                  <select id="hw-mes" defaultValue={hoy.getMonth() + 1}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #2a3a50', background: '#0d1520', color: '#e2e8f0', fontSize: 13 }}>
                    {['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'].map((n,i) => (
                      <option key={i+1} value={i+1}>{n}</option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 4 }}>Año</label>
                  <select id="hw-anio" defaultValue={hoy.getFullYear()}
                    style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #2a3a50', background: '#0d1520', color: '#e2e8f0', fontSize: 13 }}>
                    {[2025, 2026, 2027].map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
              </div>
              <div className="form-actions">
                {esActivacion ? (
                  <>
                    <button className="btn btn-secondary" onClick={() => confirmar(false)}>Activar sin forecast</button>
                    <button className="btn btn-primary" onClick={() => confirmar(true)}>Activar y generar forecast</button>
                  </>
                ) : (
                  <>
                    <button className="btn btn-secondary" onClick={() => setModalForecast(null)}>Cancelar</button>
                    <button className="btn btn-primary" onClick={() => confirmar(true)}>Generar Forecast</button>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })()}

      {confirmarEliminar && (
        <div className="modal-overlay" onClick={() => setConfirmarEliminar(null)}>
          <div className="modal" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Eliminar producto</span>
              <button className="modal-close" onClick={() => setConfirmarEliminar(null)}>✕</button>
            </div>
            <p style={{ color: "var(--text2)", marginBottom: 24 }}>
              ¿Seguro que deseas eliminar el producto <strong style={{ color: "var(--text)" }}>{confirmarEliminar}</strong>?
              Esta acción no se puede deshacer.
            </p>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={() => setConfirmarEliminar(null)}>Cancelar</button>
              <button className="btn btn-danger" onClick={() => handleEliminar(confirmarEliminar)}>Eliminar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
