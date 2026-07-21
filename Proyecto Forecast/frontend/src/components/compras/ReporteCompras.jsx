import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import * as XLSX from 'xlsx'
import { useAuth } from '../../context/AuthContext'

const API = '/api'

const clp = n => n == null ? '—' : Math.round(n).toLocaleString('es-CL')
const num = n => n == null ? '—' : Number(n).toLocaleString('es-CL')

const SEMAFORO = {
  0: { label: 'OK',       bg: '#d1fae5', color: '#065f46', dot: '#10b981' },
  1: { label: 'Riesgo',   bg: '#fef3c7', color: '#92400e', dot: '#f59e0b' },
  2: { label: 'Crítico',  bg: '#fee2e2', color: '#991b1b', dot: '#ef4444' },
}

const MESES_POST = ['Sep','Oct','Nov','Dic']

export default function ReporteCompras() {
  const { authFetch, isAdmin } = useAuth()
  const [data,         setData]        = useState(null)
  const [loading,      setLoading]     = useState(false)
  const [filtros,      setFiltros]     = useState({ marca_id:'', categoria_id:'', temporada_id:'', pareto:'', solo_faltante: false })
  const [marcas,       setMarcas]      = useState([])
  const [categorias,   setCategorias]  = useState([])
  const [temporadas,   setTemporadas]  = useState([])
  const [busqueda,     setBusqueda]    = useState('')
  const [ordenCol,     setOrdenCol]    = useState('semaforo')
  const [ordenDir,     setOrdenDir]    = useState('desc')
  const [editStock,    setEditStock]   = useState(null)   // {sku, value}
  const [stockOvr,     setStockOvr]    = useState({})     // {sku: total_override}
  const [filtroSemaforo, setFiltroSemaforo] = useState(null) // null=todos, 0=verde, 1=amarillo, 2=rojo
  const [hoveredRow, setHoveredRow]         = useState(null)
  const scrollRef   = useRef(null)
  const rafRef      = useRef(null)

  const onMouseMove = useCallback((e) => {
    const el = scrollRef.current
    if (!el) return
    const { left, right, width } = el.getBoundingClientRect()
    const ZONE = Math.min(120, width * 0.15)   // zona de activación: 120px o 15% del ancho
    const x = e.clientX
    let speed = 0
    if (x < left + ZONE)  speed = -((ZONE - (x - left))  / ZONE) * 14
    if (x > right - ZONE) speed =  ((ZONE - (right - x)) / ZONE) * 14
    cancelAnimationFrame(rafRef.current)
    if (speed !== 0) {
      const scroll = () => { el.scrollLeft += speed; rafRef.current = requestAnimationFrame(scroll) }
      rafRef.current = requestAnimationFrame(scroll)
    }
  }, [])

  const onMouseLeave = useCallback(() => { cancelAnimationFrame(rafRef.current) }, [])

  useEffect(() => {
    authFetch(`${API}/marcas/`).then(r=>r.ok?r.json():[]).then(setMarcas).catch(()=>{})
    authFetch(`${API}/categorias/`).then(r=>r.ok?r.json():[]).then(setCategorias).catch(()=>{})
    authFetch(`${API}/temporadas/`).then(r=>r.ok?r.json():[]).then(setTemporadas).catch(()=>{})
    cargar()
  }, [])

  async function cargar(f = filtros) {
    setLoading(true)
    try {
      const qs = new URLSearchParams()
      if (f.marca_id)       qs.set('marca_id',     f.marca_id)
      if (f.categoria_id)   qs.set('categoria_id', f.categoria_id)
      if (f.temporada_id)   qs.set('temporada_id', f.temporada_id)
      if (f.pareto)         qs.set('pareto',        f.pareto)
      if (f.solo_faltante)  qs.set('solo_faltante', 'true')
      const r = await authFetch(`${API}/compras?${qs}`)
      if (!r.ok) throw new Error(await r.text())
      setData(await r.json())
    } catch(e) { alert('Error al cargar: ' + e.message) }
    finally { setLoading(false) }
  }

  async function actualizarCostos() {
    if (!window.confirm('¿Actualizar costos desde ventas sincronizadas? Esto puede tomar unos segundos.')) return
    try {
      const r = await authFetch(`${API}/compras/actualizar-costos`, { method: 'POST' })
      const d = await r.json()
      alert(`Costos actualizados: ${d.actualizados} productos. Sin costo: ${d.sin_costo}`)
      cargar()
    } catch(e) { alert('Error: ' + e.message) }
  }

  function aplicarFiltros() { cargar(filtros) }

  const filasFiltradas = useMemo(() => {
    if (!data) return []
    let f = data.filas
    if (filtroSemaforo !== null) f = f.filter(r => r.semaforo === filtroSemaforo)
    if (busqueda) {
      const b = busqueda.toLowerCase()
      f = f.filter(r => r.sku.toLowerCase().includes(b) || r.descripcion?.toLowerCase().includes(b) || r.marca?.toLowerCase().includes(b))
    }
    f = [...f].sort((a,b) => {
      let va = a[ordenCol], vb = b[ordenCol]
      if (typeof va === 'string') va = va?.toLowerCase()
      if (typeof vb === 'string') vb = vb?.toLowerCase()
      if (va == null) return 1; if (vb == null) return -1
      return ordenDir === 'asc' ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1)
    })
    return f
  }, [data, busqueda, ordenCol, ordenDir, filtroSemaforo])

  async function guardarStock(sku, valor, llegadasTotal) {
    const n = parseInt(valor, 10)
    if (isNaN(n) || n < 0) { setEditStock(null); return }
    try {
      await authFetch(`${API}/stock/bulk-upsert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify([{ sku, stock_jun: n }]),
      })
      // Mostrar total actualizado (stock_jun nuevo + llegadas existentes)
      setStockOvr(prev => ({ ...prev, [sku]: n + (llegadasTotal || 0) }))
    } catch(e) { alert('Error guardando stock: ' + e.message) }
    finally { setEditStock(null) }
  }

  function toggleOrden(col) {
    if (ordenCol === col) setOrdenDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setOrdenCol(col); setOrdenDir('desc') }
  }

  function exportarExcel() {
    if (!data) return
    const ws_data = [
      ['SKU','Marca','Cat. Principal','Subcategoría','Tipo de Producto','Temporada','Descripción','Pareto',
       'Stock Jun','Leg Jun','Leg Jul','Leg Ago','Leg Sep','Leg Oct','Leg Nov','Leg Dic','Stock Total',
       'Fc Jun','Fc Jul','Fc Ago','Fc Sep','Fc Oct','Fc Nov','Fc Dic',
       'Fc Pre-Arribo (Jun-Ago)','Fc Post-Arribo (Sep-Dic)','A Comprar',
       'Costo Unit.','Importe Compra','Venta Perdida','Semáforo'],
      ...filasFiltradas.map(r => [
        r.sku, r.marca, r.categoria, r.subcategoria, r.tipo_producto, r.temporada, r.descripcion, r.pareto,
        r.stock_jun,
        r.llegadas?.Jun||0, r.llegadas?.Jul||0, r.llegadas?.Ago||0,
        r.llegadas?.Sep||0, r.llegadas?.Oct||0, r.llegadas?.Nov||0, r.llegadas?.Dic||0,
        r.stock_disponible,
        r.meses.Jun, r.meses.Jul, r.meses.Ago,
        r.meses.Sep, r.meses.Oct, r.meses.Nov, r.meses.Dic,
        r.fc_pre, r.fc_post, r.a_comprar,
        r.costo_unitario, r.importe_compra, r.venta_neta_fc,
        ['OK','Riesgo','Crítico'][r.semaforo],
      ])
    ]
    const wb = XLSX.utils.book_new()
    const ws = XLSX.utils.aoa_to_sheet(ws_data)
    ws['!cols'] = [8,12,14,12,32,6,10,...Array(12).fill(8),10,10,12].map(w=>({wch:w}))
    XLSX.utils.book_append_sheet(wb, ws, 'Reporte Compras')

    // Hoja resumen
    const meta = data.meta
    const ws_meta = XLSX.utils.aoa_to_sheet([
      ['Fecha cálculo', meta.fecha_calculo],
      ['Lead time', `${meta.lead_time_dias} días`],
      ['Fecha arribo estimada', meta.fecha_arribo],
      ['Mes arribo', meta.mes_arribo],
      [''],
      ['Total productos', meta.total_productos],
      ['Total unidades a comprar', meta.total_faltante],
      ['Importe total compra (neto)', meta.total_importe],
      [''],
      ['Críticos (rojo)', meta.rojos],
      ['En riesgo (amarillo)', meta.amarillos],
      ['Sin problemas (verde)', meta.verdes],
    ])
    XLSX.utils.book_append_sheet(wb, ws_meta, 'Resumen')
    XLSX.writeFile(wb, `ReporteCompras_${meta.fecha_calculo}.xlsx`)
  }

  // Anchos acumulados para sticky left (Estado, SKU, Marca, Descripción, Subcategoría, Tipo de Producto, Temporada, Par.)
  const STICKY_WIDTHS = [80, 65, 80, 200, 110, 110, 90, 38]
  const STICKY_LEFT   = STICKY_WIDTHS.reduce((acc, w, i) => { acc.push(i === 0 ? 0 : acc[i-1] + STICKY_WIDTHS[i-1]); return acc }, [])
  const STICKY_TOTAL  = STICKY_WIDTHS.reduce((a, b) => a + b, 0)

  const stickyTh = (i, extra = {}) => ({
    position: 'sticky', left: STICKY_LEFT[i], zIndex: 3,
    background: '#1e293b', color: '#e2e8f0', fontSize: 11,
    whiteSpace: 'nowrap', padding: '6px 8px',
    borderRight: i === STICKY_WIDTHS.length - 1 ? '2px solid #475569' : '1px solid #334155',
    minWidth: STICKY_WIDTHS[i], maxWidth: STICKY_WIDTHS[i],
    ...extra,
  })

  const stickyTd = (i, bg, extra = {}) => ({
    position: 'sticky', left: STICKY_LEFT[i], zIndex: 2,
    background: bg,
    borderRight: i === STICKY_WIDTHS.length - 1 ? '2px solid #cbd5e1' : '1px solid #e2e8f0',
    padding: '5px 8px',
    ...extra,
  })

  const Th = ({col, children, style: extraStyle}) => (
    <th onClick={() => toggleOrden(col)} style={{cursor:'pointer', whiteSpace:'nowrap', padding:'6px 8px',
      background:'#1e293b', color:'#e2e8f0', fontSize:11, userSelect:'none',
      borderRight:'1px solid #334155', ...extraStyle}}>
      {children} {ordenCol===col ? (ordenDir==='asc'?'↑':'↓') : ''}
    </th>
  )

  if (!data && loading) return (
    <div style={{padding:32, textAlign:'center', color:'#64748b'}}>
      Calculando reporte de compras…
    </div>
  )

  const meta = data?.meta

  return (
    <div style={{fontFamily:'system-ui,sans-serif', padding:16}}>
      {/* Header */}
      <div style={{display:'flex', alignItems:'center', gap:12, marginBottom:16}}>
        <h2 style={{margin:0, fontSize:18, color:'#1e293b'}}>Reporte de Compras 2026</h2>
        {meta && (
          <span style={{fontSize:12, color:'#64748b'}}>
            Lead time {meta.lead_time_dias}d — arribo estimado{' '}
            <strong>{meta.fecha_arribo}</strong> (mes {meta.mes_arribo})
          </span>
        )}
        <div style={{marginLeft:'auto', display:'flex', gap:8}}>
          <button onClick={aplicarFiltros} disabled={loading}
            style={{padding:'6px 14px', background:'#3b82f6', color:'#fff', border:'none', borderRadius:6, cursor:'pointer', fontSize:13}}>
            {loading ? 'Cargando…' : 'Actualizar'}
          </button>
          <button onClick={exportarExcel} disabled={!data}
            style={{padding:'6px 14px', background:'#16a34a', color:'#fff', border:'none', borderRadius:6, cursor:'pointer', fontSize:13}}>
            ↓ Excel
          </button>
          {isAdmin && (
            <>
              <label style={{padding:'6px 14px', background:'#0369a1', color:'#fff', borderRadius:6, cursor:'pointer', fontSize:13, display:'inline-block'}}>
                ↑ Subir Stock
                <input type="file" accept=".xlsx,.xls" style={{display:'none'}}
                  onChange={async e => {
                    const f = e.target.files[0]; if (!f) return
                    const form = new FormData(); form.append('file', f)
                    try {
                      const r = await authFetch(`${API}/stock/upload-excel`, { method: 'POST', body: form })
                      const d = await r.json()
                      alert(`Stock cargado: ${d.upserted} productos. Ignorados: ${d.ignorados}`)
                      cargar()
                    } catch(err) { alert('Error: ' + err.message) }
                    e.target.value = ''
                  }} />
              </label>
              <button onClick={actualizarCostos}
                style={{padding:'6px 14px', background:'#7c3aed', color:'#fff', border:'none', borderRadius:6, cursor:'pointer', fontSize:13}}>
                ⟳ Actualizar Costos
              </button>
            </>
          )}
        </div>
      </div>

      {/* KPIs */}
      {meta && (
        <div style={{display:'flex', gap:12, marginBottom:16, flexWrap:'wrap'}}>
          {[
            { label:'Críticos',     val: meta.rojos,     bg:'#fee2e2', color:'#991b1b', sem: 2 },
            { label:'En riesgo',    val: meta.amarillos,  bg:'#fef3c7', color:'#92400e', sem: 1 },
            { label:'Sin problema', val: meta.verdes,     bg:'#d1fae5', color:'#065f46', sem: 0 },
            { label:'Total a comprar', val: num(meta.total_faltante) + ' un.', bg:'#eff6ff', color:'#1e3a8a', sem: null },
            { label:'Importe estimado', val: '$' + clp(meta.total_importe), bg:'#f5f3ff', color:'#3730a3', sem: null },
          ].map(k => {
            const activo = k.sem !== null && filtroSemaforo === k.sem
            return (
              <div key={k.label}
                onClick={() => k.sem !== null && setFiltroSemaforo(activo ? null : k.sem)}
                style={{
                  background: k.bg, color: k.color, borderRadius:8, padding:'10px 16px', minWidth:120,
                  cursor: k.sem !== null ? 'pointer' : 'default',
                  outline: activo ? `2px solid ${k.color}` : 'none',
                  transform: activo ? 'scale(1.03)' : 'none',
                  transition: 'transform .1s, outline .1s',
                }}>
                <div style={{fontSize:11, opacity:.75}}>{k.label}{activo ? ' ✕' : ''}</div>
                <div style={{fontSize:20, fontWeight:700}}>{k.val}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Filtros */}
      <div style={{display:'flex', gap:8, marginBottom:12, flexWrap:'wrap', alignItems:'center'}}>
        <input value={busqueda} onChange={e=>setBusqueda(e.target.value)}
          placeholder="Buscar SKU / descripción…"
          style={{padding:'5px 10px', border:'1px solid #cbd5e1', borderRadius:6, fontSize:13, width:200}}/>
        <select value={filtros.marca_id} onChange={e=>setFiltros(f=>({...f,marca_id:e.target.value}))}
          style={{padding:'5px 8px', border:'1px solid #cbd5e1', borderRadius:6, fontSize:13}}>
          <option value="">Todas las marcas</option>
          {marcas.map(m=><option key={m.id} value={m.id}>{m.nombre}</option>)}
        </select>
        <select value={filtros.categoria_id} onChange={e=>setFiltros(f=>({...f,categoria_id:e.target.value}))}
          style={{padding:'5px 8px', border:'1px solid #cbd5e1', borderRadius:6, fontSize:13}}>
          <option value="">Todas las categorías</option>
          {categorias.map(c=><option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <select value={filtros.temporada_id} onChange={e=>setFiltros(f=>({...f,temporada_id:e.target.value}))}
          style={{padding:'5px 8px', border:'1px solid #cbd5e1', borderRadius:6, fontSize:13}}>
          <option value="">Todas las temporadas</option>
          {temporadas.map(t=><option key={t.id} value={t.id}>{t.nombre}</option>)}
        </select>
        <select value={filtros.pareto} onChange={e=>setFiltros(f=>({...f,pareto:e.target.value}))}
          style={{padding:'5px 8px', border:'1px solid #cbd5e1', borderRadius:6, fontSize:13}}>
          <option value="">Pareto A+B+C</option>
          <option value="A">Solo A</option>
          <option value="B">Solo B</option>
          <option value="C">Solo C</option>
        </select>
        <label style={{display:'flex', alignItems:'center', gap:4, fontSize:13, color:'#475569'}}>
          <input type="checkbox" checked={filtros.solo_faltante}
            onChange={e=>setFiltros(f=>({...f,solo_faltante:e.target.checked}))}/>
          Solo con faltante
        </label>
      </div>

      {/* Tabla */}
      {filasFiltradas.length === 0 ? (
        <div style={{padding:32, textAlign:'center', color:'#94a3b8'}}>Sin datos</div>
      ) : (
        <div ref={scrollRef} onMouseMove={onMouseMove} onMouseLeave={onMouseLeave}
          style={{overflowX:'auto', border:'1px solid #e2e8f0', borderRadius:8}}>
          <table style={{borderCollapse:'collapse', width:'100%', fontSize:12}}>
            <thead>
              <tr>
                <th onClick={() => toggleOrden('semaforo')} style={{...stickyTh(0), cursor:'pointer', userSelect:'none'}}>Estado {ordenCol==='semaforo'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('sku')}      style={{...stickyTh(1), cursor:'pointer', userSelect:'none'}}>SKU {ordenCol==='sku'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('marca')}    style={{...stickyTh(2), cursor:'pointer', userSelect:'none'}}>Marca {ordenCol==='marca'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('descripcion')} style={{...stickyTh(3), cursor:'pointer', userSelect:'none'}}>Descripción {ordenCol==='descripcion'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('subcategoria')} style={{...stickyTh(4), cursor:'pointer', userSelect:'none'}}>Subcategoría {ordenCol==='subcategoria'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('tipo_producto')} style={{...stickyTh(5), cursor:'pointer', userSelect:'none'}}>Tipo de Producto {ordenCol==='tipo_producto'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('temporada')} style={{...stickyTh(6), cursor:'pointer', userSelect:'none'}}>Temporada {ordenCol==='temporada'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <th onClick={() => toggleOrden('pareto')}   style={{...stickyTh(7), cursor:'pointer', userSelect:'none'}}>Par. {ordenCol==='pareto'?(ordenDir==='asc'?'↑':'↓'):''}</th>
                <Th col="stock_jun">St. Jun</Th>
                {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                  <th key={`leg_${m}`} style={{
                    padding:'6px 8px', background:'#064e3b',
                    color:'#6ee7b7', fontSize:11, borderRight:'1px solid #065f46', whiteSpace:'nowrap'
                  }}>Leg {m}</th>
                ))}
                <Th col="stock_disponible">Stock Total</Th>
                {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                  <th key={m} style={{
                    padding:'6px 8px', background: MESES_POST.includes(m) ? '#1e3a8a' : '#1e293b',
                    color:'#e2e8f0', fontSize:11, borderRight:'1px solid #334155', whiteSpace:'nowrap'
                  }}>{m}</th>
                ))}
                <Th col="fc_pre">Fc Pre</Th>
                <Th col="fc_post">Fc Post</Th>
                <Th col="a_comprar">A Comprar</Th>
                <Th col="importe_compra">Importe</Th>
                <Th col="venta_neta_fc">Venta Perdida</Th>
              </tr>
            </thead>
            <tbody>
              {filasFiltradas.map((r,i) => {
                const s = SEMAFORO[r.semaforo]
                const isHovered = hoveredRow === r.sku
                const bgBase = isHovered
                  ? (r.semaforo === 2 ? '#fff1f2' : r.semaforo === 1 ? '#fffbeb' : '#f0fdf4')
                  : (i%2===0 ? '#fff' : '#f8fafc')
                return (
                  <tr key={r.sku}
                    onMouseEnter={() => setHoveredRow(r.sku)}
                    onMouseLeave={() => setHoveredRow(null)}
                    style={{background: bgBase, transition: 'background 0.1s'}}>
                    <td style={stickyTd(0, bgBase, {textAlign:'center'})}>
                      <span style={{
                        display:'inline-block', padding:'2px 8px', borderRadius:12,
                        background:s.bg, color:s.color, fontWeight:600, fontSize:11
                      }}>{s.label}</span>
                    </td>
                    <td style={stickyTd(1, bgBase, {fontFamily:'monospace', fontWeight:600, color:'#1e293b'})}>{r.sku}</td>
                    <td style={stickyTd(2, bgBase, {color:'#475569'})}>{r.marca}</td>
                    <td style={stickyTd(3, bgBase, {maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:'#1e293b'})}
                        title={r.descripcion}>{r.descripcion}</td>
                    <td style={stickyTd(4, bgBase, {maxWidth:110, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:'#475569', fontSize:11})}
                        title={r.subcategoria}>{r.subcategoria || '—'}</td>
                    <td style={stickyTd(5, bgBase, {maxWidth:110, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color: r.tipo_producto ? '#475569' : '#ef4444', fontSize:11})}
                        title={r.tipo_producto}>{r.tipo_producto || '—'}</td>
                    <td style={stickyTd(6, bgBase, {color:'#475569', whiteSpace:'nowrap', fontSize:11})}>{r.temporada || '—'}</td>
                    <td style={stickyTd(7, bgBase, {textAlign:'center'})}>
                      {r.pareto && (
                        <span style={{
                          display:'inline-block', width:20, height:20, lineHeight:'20px',
                          borderRadius:4, textAlign:'center', fontWeight:700, fontSize:11,
                          background: r.pareto==='A' ? '#fef3c7' : r.pareto==='B' ? '#f1f5f9' : '#f0fdf4',
                          color: r.pareto==='A' ? '#92400e' : r.pareto==='B' ? '#334155' : '#166534',
                        }}>{r.pareto}</span>
                      )}
                    </td>
                    <td style={{padding:'5px 8px', textAlign:'right', color:'#064e3b', fontWeight:600, background:'#f0fdf4'}}>
                      {num(r.stock_jun)}
                    </td>
                    {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                      <td key={`leg_${m}`} style={{padding:'5px 8px', textAlign:'right', background:'#f0fdf4',
                        color: (r.llegadas?.[m]||0) > 0 ? '#065f46' : '#d1fae5'}}>
                        {(r.llegadas?.[m]||0) > 0 ? num(r.llegadas[m]) : '—'}
                      </td>
                    ))}
                    <td
                      style={{padding:'5px 8px', textAlign:'right', fontWeight:600, cursor: isAdmin ? 'pointer' : 'default',
                        color: (stockOvr[r.sku] ?? r.stock_disponible)===0 ? '#ef4444' : '#1e293b',
                        background: stockOvr[r.sku] != null ? '#fefce8' : 'transparent'}}
                      title={isAdmin ? `Click para editar Stock Jun (llegadas: ${Object.values(r.llegadas||{}).reduce((a,b)=>a+b,0)})` : ''}
                      onClick={() => { if (!isAdmin) return; const ll = Object.values(r.llegadas||{}).reduce((a,b)=>a+b,0); setEditStock({ sku: r.sku, value: String(r.stock_jun), llegadas: ll }) }}
                    >
                      {editStock?.sku === r.sku ? (
                        <input autoFocus value={editStock.value}
                          onChange={e => setEditStock(s => ({...s, value: e.target.value}))}
                          onBlur={() => guardarStock(r.sku, editStock.value, editStock.llegadas)}
                          onKeyDown={e => { if(e.key==='Enter') guardarStock(r.sku, editStock.value, editStock.llegadas); if(e.key==='Escape') setEditStock(null) }}
                          style={{width:60, textAlign:'right', border:'1px solid #3b82f6', borderRadius:4, padding:'0 4px', fontSize:12}}
                          onClick={e => e.stopPropagation()}/>
                      ) : num(stockOvr[r.sku] ?? r.stock_disponible)}
                    </td>
                    {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m => (
                      <td key={m} style={{
                        padding:'5px 8px', textAlign:'right',
                        background: MESES_POST.includes(m) ? '#eff6ff' : 'transparent',
                        color: r.meses[m] > 0 ? '#1e293b' : '#cbd5e1'
                      }}>{r.meses[m] || '—'}</td>
                    ))}
                    <td style={{padding:'5px 8px', textAlign:'right', color:'#64748b'}}
                        title={r.extra_pre > 0 ? `Propio: ${num(r.fc_pre - r.extra_pre)} + Packs: ${num(r.extra_pre)}` : ''}>
                      {num(r.fc_pre)}{r.extra_pre > 0 && <span style={{color:'#7c3aed', fontSize:10, marginLeft:2}}>P</span>}
                    </td>
                    <td style={{padding:'5px 8px', textAlign:'right', fontWeight:600}}
                        title={r.extra_post > 0 ? `Propio: ${num(r.fc_post - r.extra_post)} + Packs: ${num(r.extra_post)}` : ''}>
                      {num(r.fc_post)}{r.extra_post > 0 && <span style={{color:'#7c3aed', fontSize:10, marginLeft:2}}>P</span>}
                    </td>
                    <td style={{padding:'5px 8px', textAlign:'right', fontWeight:700,
                      color: r.comentario === 'Descontinuar' ? '#7c3aed' : r.a_comprar > 0 ? '#dc2626' : '#16a34a'}}>
                      {r.comentario === 'Descontinuar'
                        ? <span style={{fontSize:10, background:'#ede9fe', color:'#7c3aed', borderRadius:8, padding:'2px 6px'}}>No comprar</span>
                        : r.a_comprar > 0 ? num(r.a_comprar) : '✓'}
                    </td>
                    <td style={{padding:'5px 8px', textAlign:'right', color: r.importe_compra > 0 ? '#1e293b' : '#cbd5e1'}}>
                      {r.importe_compra > 0 ? '$' + clp(r.importe_compra) : '—'}
                    </td>
                    <td style={{padding:'5px 8px', textAlign:'right', color: r.a_comprar > 0 ? '#b45309' : '#cbd5e1', fontWeight: r.a_comprar > 0 ? 600 : 400}}>
                      {r.a_comprar > 0 && r.venta_neta_fc > 0 ? '$' + clp(r.venta_neta_fc) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr style={{background:'#1e293b', color:'#e2e8f0', fontWeight:700}}>
                <td colSpan={8} style={{padding:'6px 8px', fontSize:12}}>TOTAL ({filasFiltradas.length} SKUs)</td>
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12, background:'#064e3b', color:'#6ee7b7'}}>
                  {num(filasFiltradas.reduce((s,r)=>s+(r.stock_jun||0),0))}
                </td>
                {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                  <td key={`tleg_${m}`} style={{padding:'6px 8px', textAlign:'right', fontSize:12, background:'#064e3b', color:'#6ee7b7'}}>
                    {num(filasFiltradas.reduce((s,r)=>s+(r.llegadas?.[m]||0),0))}
                  </td>
                ))}
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12}}>
                  {num(filasFiltradas.reduce((s,r)=>s+r.stock_disponible,0))}
                </td>
                {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                  <td key={m} style={{padding:'6px 8px', textAlign:'right', fontSize:12,
                    background: MESES_POST.includes(m) ? '#1e3a8a' : 'transparent'}}>
                    {num(filasFiltradas.reduce((s,r)=>s+(r.meses[m]||0),0))}
                  </td>
                ))}
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12}}>
                  {num(filasFiltradas.reduce((s,r)=>s+r.fc_pre,0))}
                </td>
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12}}>
                  {num(filasFiltradas.reduce((s,r)=>s+r.fc_post,0))}
                </td>
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12, color:'#fca5a5'}}>
                  {num(filasFiltradas.reduce((s,r)=>s+r.a_comprar,0))}
                </td>
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12}}>
                  ${clp(filasFiltradas.reduce((s,r)=>s+r.importe_compra,0))}
                </td>
                <td style={{padding:'6px 8px', textAlign:'right', fontSize:12, color:'#fcd34d'}}>
                  ${clp(filasFiltradas.reduce((s,r)=>s+r.venta_neta_fc,0))}
                </td>
              </tr>
              <tr style={{background:'#0c1829', color:'#cbd5e1', fontWeight:600}}>
                <td colSpan={17} style={{padding:'5px 8px', fontSize:11, color:'#64748b', fontStyle:'italic'}}>
                  Venta Bruta FC ($)
                </td>
                {['Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map(m=>(
                  <td key={`bruto_${m}`} style={{padding:'5px 8px', textAlign:'right', fontSize:11,
                    background: MESES_POST.includes(m) ? '#172554' : '#0c1829',
                    color: MESES_POST.includes(m) ? '#bfdbfe' : '#cbd5e1',
                    borderTop:'1px solid #1e3a5f'}}>
                    ${clp(filasFiltradas.reduce((s,r)=>s+(r.meses[m]||0)*(r.precio_neto||0)*1.19, 0))}
                  </td>
                ))}
                <td style={{padding:'5px 8px', borderTop:'1px solid #1e3a5f'}}/>
                <td style={{padding:'5px 8px', borderTop:'1px solid #1e3a5f'}}/>
                <td style={{padding:'5px 8px', textAlign:'right', fontSize:11, color:'#fca5a5', borderTop:'1px solid #1e3a5f'}}>
                  ${clp(filasFiltradas.reduce((s,r)=>s+r.a_comprar*(r.precio_neto||0)*1.19, 0))}
                </td>
                <td style={{padding:'5px 8px', borderTop:'1px solid #1e3a5f'}}/>
                <td style={{padding:'5px 8px', borderTop:'1px solid #1e3a5f'}}/>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}
