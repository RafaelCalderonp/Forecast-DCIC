import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useAuth } from '../../context/AuthContext'

const clp = n => (n == null || n === 0) ? '—' : Math.round(n).toLocaleString('es-CL')
const API  = '/api'

const ARRIVAL_KEYS = [
  { qty: 'bodega_transito', eta: 'eta_transito', label: 'Tránsito' },
  { qty: 'por_arribar',     eta: 'eta_arribar',  label: 'Por arribar' },
  { qty: 'pi',              eta: 'eta_pi',        label: 'PI' },
]

export default function StockPage() {
  const { authFetch } = useAuth()
  const [stocks,    setStocks]    = useState([])
  const [productos, setProductos] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [mensaje,   setMensaje]   = useState(null)
  const [uploading, setUploading] = useState(false)
  const [filtros,   setFiltros]   = useState({ busqueda: '', temporada: '', soloFaltante: false })
  const [pendingEta, setPendingEta] = useState({})   // { 'sku|eta_key': 'YYYY-MM-DD' }

  const authFetchRef = useRef(authFetch)
  useEffect(() => { authFetchRef.current = authFetch }, [authFetch])

  const cargar = useCallback(async () => {
    setLoading(true)
    try {
      const [sRes, pRes] = await Promise.all([
        authFetchRef.current(`${API}/stock/`),
        authFetchRef.current(`${API}/productos/`),
      ])
      const sData = sRes.ok ? await sRes.json() : []
      const pData = pRes.ok ? await pRes.json() : []
      setStocks(sData)
      setProductos(pData)
    } catch (e) {
      mostrarMensaje('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  async function sincronizarYCargar() {
    setLoading(true)
    try {
      const res = await authFetchRef.current(`${API}/stock/sync-desde-api`, { method: 'POST' })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      mostrarMensaje('success', `Stock sincronizado: ${data.actualizados} SKUs actualizados`)
      await cargar()
    } catch (e) {
      mostrarMensaje('error', `Error al sincronizar stock: ${e.message}`)
      setLoading(false)
    }
  }

  const mostrarMensaje = (tipo, texto) => {
    setMensaje({ tipo, texto })
    setTimeout(() => setMensaje(null), 4000)
  }

  // Merge stock + producto
  const rows = useMemo(() => {
    const prodMap = {}
    productos.forEach(p => { prodMap[p.sku] = p })
    return stocks.map(s => ({ ...s, _prod: prodMap[s.sku] || null }))
  }, [stocks, productos])

  // Temporadas disponibles
  const temporadas = useMemo(() => {
    const set = new Set()
    rows.forEach(r => { if (r._prod?.temporada?.nombre) set.add(r._prod.temporada.nombre) })
    return [...set].sort()
  }, [rows])

  // Filtrado
  const filtradas = useMemo(() => {
    const q = filtros.busqueda.toLowerCase()
    return rows.filter(r => {
      const p = r._prod
      if (filtros.temporada && p?.temporada?.nombre !== filtros.temporada) return false
      if (filtros.soloFaltante) {
        const total = (r.stock_base||0) + (r.stock_full_ml||0) + (r.stock_full_fala||0) +
                      (r.bodega_transito||0) + (r.por_arribar||0) + (r.pi||0)
        if (total > 0) return false
      }
      if (!q) return true
      return (
        r.sku.toLowerCase().includes(q) ||
        (p?.descripcion || '').toLowerCase().includes(q) ||
        (p?.marca?.nombre || '').toLowerCase().includes(q)
      )
    })
  }, [rows, filtros])

  // Guardar ETA al cambiar el date input
  async function guardarEta(sku, etaKey, valor) {
    const key = `${sku}|${etaKey}`
    setPendingEta(prev => ({ ...prev, [key]: 'saving' }))
    try {
      const res = await authFetchRef.current(`${API}/stock/${sku}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [etaKey]: valor || null }),
      })
      if (!res.ok) throw new Error(await res.text())
      // Actualizar local
      setStocks(prev => prev.map(s =>
        s.sku === sku ? { ...s, [etaKey]: valor || null } : s
      ))
      setPendingEta(prev => { const n = { ...prev }; delete n[key]; return n })
    } catch (e) {
      mostrarMensaje('error', `Error al guardar ETA: ${e.message}`)
      setPendingEta(prev => { const n = { ...prev }; delete n[key]; return n })
    }
  }

  // Descargar archivo de muestra
  async function descargarMuestra() {
    const XLSX = await import('xlsx')
    const cols = [
      'SKU', 'Stock Base', 'Full ML', 'Full Falabella',
      'Bodega Tránsito', 'ETA Tránsito',
      'Por Arribar', 'ETA Arribar',
      'PI', 'ETA PI',
    ]
    const filas = [
      ['R6683', 12, 0, 0, 500, '2026-08-15', 0, '', 0, ''],
      ['ABC123', 50, 10, 5, 0, '', 200, '2026-09-01', 100, '2026-10-01'],
      ['XYZ999', 0, 0, 0, 0, '', 0, '', 0, ''],
    ]
    const ws = XLSX.utils.aoa_to_sheet([cols, ...filas])
    // Ancho de columnas
    ws['!cols'] = [10,12,10,14,16,14,12,12,8,10].map(w => ({ wch: w }))
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Inventario')
    XLSX.writeFile(wb, 'muestra_inventario_stock.xlsx')
  }

  // Upload Excel
  async function handleExcel(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await authFetchRef.current(`${API}/stock/upload-excel`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || JSON.stringify(data))
      mostrarMensaje('success', `Importado: ${data.upserted} SKUs actualizados, ${data.ignorados || 0} ignorados`)
      cargar()
    } catch (e) {
      mostrarMensaje('error', `Error al importar: ${e.message}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const totalStock = (r) =>
    (r.stock_base||0) + (r.stock_full_ml||0) + (r.stock_full_fala||0) +
    (r.bodega_transito||0) + (r.por_arribar||0) + (r.pi||0)

  const totalLlegadas = (r) =>
    (r.bodega_transito||0) + (r.por_arribar||0) + (r.pi||0)

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Stock e Inventario</div>
          <div className="page-subtitle">{filtradas.length} / {rows.length} SKUs · Gestiona cantidades y fechas de llegada</div>
        </div>
        <div className="header-actions">
          <button
            onClick={descargarMuestra}
            style={{
              padding: '7px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              background: '#ECFDF5', color: '#34d399', borderRadius: 6, border: '1px solid #065f46',
            }}>
            ↓ Archivo muestra
          </button>
          <label style={{
            padding: '7px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: '#E0F2FE', color: '#14B8A6', borderRadius: 6, border: '1px solid #0D9488',
          }}>
            {uploading ? '…Importando' : '↑ Importar Excel'}
            <input type="file" accept=".xlsx,.xls" onChange={handleExcel} style={{ display: 'none' }} disabled={uploading} />
          </label>
          <button className="btn btn-secondary btn-sm" onClick={sincronizarYCargar} disabled={loading} title="Sincroniza con dcic-stock-loader y refresca">
            {loading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : '↻'} Actualizar
          </button>
        </div>
      </div>

      {mensaje && (
        <div className={`alert alert-${mensaje.tipo === 'success' ? 'success' : 'error'}`} style={{ margin: '0 0 12px' }}>
          {mensaje.texto}
        </div>
      )}

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          className="search-input"
          placeholder="SKU, descripción, marca…"
          value={filtros.busqueda}
          onChange={e => setFiltros(p => ({ ...p, busqueda: e.target.value }))}
          style={{ width: 260 }}
        />
        <select
          className="form-select"
          value={filtros.temporada}
          onChange={e => setFiltros(p => ({ ...p, temporada: e.target.value }))}
          style={{ width: 180, padding: '6px 10px', fontSize: 12 }}
        >
          <option value=''>Todas las temporadas</option>
          {temporadas.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#666666', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={filtros.soloFaltante}
            onChange={e => setFiltros(p => ({ ...p, soloFaltante: e.target.checked }))}
          />
          Solo sin stock
        </label>

        {/* Stats rápidos */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: 12, color: '#666666' }}>
          <span><span style={{ color: '#111111', fontWeight: 600 }}>{rows.filter(r => totalStock(r) === 0).length}</span> sin stock</span>
          <span><span style={{ color: '#f59e0b', fontWeight: 600 }}>{rows.filter(r => totalLlegadas(r) > 0 && !r.eta_transito && !r.eta_arribar && !r.eta_pi).length}</span> llegadas sin ETA</span>
          <span><span style={{ color: '#14B8A6', fontWeight: 600 }}>{rows.filter(r => totalLlegadas(r) > 0 && (r.eta_transito || r.eta_arribar || r.eta_pi)).length}</span> con ETA asignada</span>
        </div>
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center' }}><span className="spinner" /></div>
        ) : filtradas.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">⊡</div>
            <div>Sin resultados</div>
          </div>
        ) : (
          <table style={{ fontSize: 12, width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#DEDEDE', borderBottom: '2px solid #CCCCCC' }}>
                <th style={th()}>SKU</th>
                <th style={th(200)}>Descripción</th>
                <th style={th()}>Marca</th>
                <th style={th()}>Temporada</th>
                <th style={{ ...th(), textAlign: 'right' }}>Base</th>
                <th style={{ ...th(), textAlign: 'right' }}>Full ML</th>
                <th style={{ ...th(), textAlign: 'right' }}>Full Fala</th>
                <th style={{ ...th(), textAlign: 'right', color: '#f59e0b' }}>Tránsito</th>
                <th style={{ ...th(120), color: '#f59e0b' }}>ETA Tránsito</th>
                <th style={{ ...th(), textAlign: 'right', color: '#a78bfa' }}>Por Arribar</th>
                <th style={{ ...th(120), color: '#a78bfa' }}>ETA Arribar</th>
                <th style={{ ...th(), textAlign: 'right', color: '#34d399' }}>PI</th>
                <th style={{ ...th(120), color: '#34d399' }}>ETA PI</th>
                <th style={{ ...th(), textAlign: 'right', borderLeft: '2px solid #CCCCCC', color: '#00c9a7', fontWeight: 700 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((r, idx) => {
                const p = r._prod
                const total = totalStock(r)
                const esInvierno = p?.temporada?.nombre?.toLowerCase().includes('invierno')
                const sinStock = total === 0
                const hayLlegada = totalLlegadas(r) > 0
                const faltaEta = hayLlegada && !r.eta_transito && !r.eta_arribar && !r.eta_pi
                const rowBg = idx % 2 === 0 ? '#F5F5F5' : '#EBEBEB'

                return (
                  <tr key={r.sku} style={{ background: rowBg, borderBottom: '1px solid #DDDDDD' }}>
                    <td style={td()}><span style={{ fontFamily: 'var(--mono)', color: '#14B8A6' }}>{r.sku}</span></td>
                    <td style={{ ...td(200), color: '#333333' }} title={p?.descripcion}>
                      {esInvierno && <span style={{ fontSize: 9, background: '#E0F2FE', color: '#14B8A6', borderRadius: 3, padding: '1px 4px', marginRight: 4, fontWeight: 700 }}>INV</span>}
                      {(p?.descripcion || '').slice(0, 36)}{(p?.descripcion||'').length > 36 ? '…' : ''}
                    </td>
                    <td style={td()}><span style={{ fontSize: 11, color: '#666666' }}>{p?.marca?.nombre || '—'}</span></td>
                    <td style={td()}><span style={{ fontSize: 11, color: '#666666' }}>{p?.temporada?.nombre || '—'}</span></td>
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: sinStock && !hayLlegada ? '#ef4444' : '#111111' }}>{clp(r.stock_base)}</td>
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: '#666666' }}>{clp(r.stock_full_ml)}</td>
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: '#666666' }}>{clp(r.stock_full_fala)}</td>

                    {/* Tránsito + ETA */}
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: '#f59e0b' }}>{clp(r.bodega_transito)}</td>
                    <EtaCell sku={r.sku} etaKey="eta_transito" value={r.eta_transito} qty={r.bodega_transito}
                      pending={pendingEta[`${r.sku}|eta_transito`]} onSave={guardarEta} color="#f59e0b" />

                    {/* Por arribar + ETA */}
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: '#a78bfa' }}>{clp(r.por_arribar)}</td>
                    <EtaCell sku={r.sku} etaKey="eta_arribar" value={r.eta_arribar} qty={r.por_arribar}
                      pending={pendingEta[`${r.sku}|eta_arribar`]} onSave={guardarEta} color="#a78bfa" />

                    {/* PI + ETA */}
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', color: '#34d399' }}>{clp(r.pi)}</td>
                    <EtaCell sku={r.sku} etaKey="eta_pi" value={r.eta_pi} qty={r.pi}
                      pending={pendingEta[`${r.sku}|eta_pi`]} onSave={guardarEta} color="#34d399" />

                    {/* Total */}
                    <td style={{ ...td(), textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 700,
                      borderLeft: '2px solid #CCCCCC',
                      color: total === 0 ? '#ef4444' : faltaEta ? '#f59e0b' : '#00c9a7' }}>
                      {clp(total)}
                      {faltaEta && <span style={{ fontSize: 9, marginLeft: 4, color: '#f59e0b' }}>⚠</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function EtaCell({ sku, etaKey, value, qty, pending, onSave, color }) {
  const [local, setLocal] = useState(value ? value.slice(0, 10) : '')

  useEffect(() => { setLocal(value ? value.slice(0, 10) : '') }, [value])

  if (!qty) {
    return <td style={td(120)}><span style={{ color: '#CCCCCC', fontSize: 11 }}>—</span></td>
  }

  const saving = pending === 'saving'

  return (
    <td style={{ ...td(120), padding: '2px 6px' }}>
      <input
        type="date"
        value={local}
        onChange={e => setLocal(e.target.value)}
        onBlur={() => { if (local !== (value ? value.slice(0, 10) : '')) onSave(sku, etaKey, local) }}
        disabled={saving}
        style={{
          width: '100%', fontSize: 11, padding: '3px 6px', borderRadius: 4,
          border: `1px solid ${local ? color : '#ef444460'}`,
          background: local ? '#FFFFFF' : '#FEF2F2',
          color: local ? color : '#ef4444',
          cursor: 'pointer', outline: 'none',
        }}
        title={local ? `ETA: ${local}` : 'Sin fecha de llegada — asignar ETA'}
      />
      {saving && <span style={{ fontSize: 9, color: '#666666' }}>…</span>}
    </td>
  )
}

const th  = (w) => ({
  padding: '8px 10px', color: '#666666', fontWeight: 600, fontSize: 11, background: '#E0E0E0',
  letterSpacing: '0.5px', textTransform: 'uppercase', textAlign: 'left',
  whiteSpace: 'nowrap', minWidth: w || undefined,
})
const td  = (w) => ({
  padding: '5px 10px', whiteSpace: 'nowrap', minWidth: w || undefined,
})
