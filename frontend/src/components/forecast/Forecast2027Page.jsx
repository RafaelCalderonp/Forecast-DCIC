import { useState, useEffect, useCallback, useMemo, useRef } from "react"
import { useAuth } from "../../context/AuthContext"
import MultiSelect from "../ui/MultiSelect"
import * as XLSX from "xlsx"

const API = "/api"
const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

const clp  = n => n == null ? '—' : Math.round(n).toLocaleString('es-CL')
const mclp = n => n == null ? '—' : Math.round(n).toLocaleString('es-CL')

const EVENTOS_DEFAULT = {
  cyberday:    { mes: 5,  label: 'Cyber Day',    color: '#1d4ed8' },
  cybermonday: { mes: 11, label: 'Cyber Monday', color: '#7c3aed' },
  blackfriday: { mes: 11, label: 'Black Friday', color: '#1E293B' },
}

// Columnas fijas
const COLS = [
  { key: 'marca',         label: 'Marca',            w: 72  },
  { key: 'sku',           label: 'SKU',              w: 72  },
  { key: 'descripcion',   label: 'Descripción',      w: 200 },
  { key: 'subcategoria',  label: 'Subcategoría',     w: 120 },
  { key: 'tipo_producto', label: 'Tipo de Producto', w: 120 },
  { key: 'temporada',     label: 'Temporada',        w: 90  },
]
const LEFT = COLS.reduce((a, c, i) => { a[i] = i === 0 ? 0 : a[i-1] + COLS[i-1].w; return a }, {})
const FROZEN_W = COLS.reduce((s, c) => s + c.w, 0)

const thFijo = i => ({
  position: 'sticky', left: LEFT[i], zIndex: 3,
  background: '#F3F3F3', color: '#666666',
  fontSize: 11, fontWeight: 700, padding: '6px 8px',
  borderRight: '1px solid #CCCCCC', borderBottom: '2px solid #0D9488',
  whiteSpace: 'nowrap', minWidth: COLS[i].w, maxWidth: COLS[i].w,
})
const tdFijo = (i, bg) => ({
  position: 'sticky', left: LEFT[i], zIndex: 2,
  background: bg, fontSize: 11, padding: '4px 8px',
  borderRight: '1px solid #CCCCCC', borderBottom: '1px solid #CCCCCC',
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  maxWidth: COLS[i].w,
})

// Recomendación del Panel de Expertos (4 especialistas, junio 2026)
const PANEL = {
  consenso: 11,
  conservador: 6,
  optimista: 18,
  expertos: [
    { rol: 'Economista macroeconómico', valor: 12 },
    { rol: 'Especialista retail/e-commerce', valor: 12 },
    { rol: 'Analista financiero importadoras', valor: 10 },
    { rol: 'Estratega de negocios', valor: 10 },
  ],
  justificacion: 'El ciclo de expansión 2024–2025 (+37.5%) fue puntual (apertura canales marketplace). Metodología aprobada: Suavizado Exponencial Ponderado (α=0.75). Meses con dato real 2026 (Ene–May): base = qty_2026_real × tasa. Meses sin dato 2026 (Jun–Dic): base = 0.75×qty_2025 + 0.25×qty_2024, luego × tasa. Corrección crítica: el modelo anterior proyectaba desde 2024 ignorando 2025 y 2026, generando resultados absurdos (Ene-27: 409M vs Ene-26 real: 622M).',
  advertencia: 'No usar tasa >18% sin nueva palanca de canal. Para 2028 en adelante recalibrar con datos reales de 2026 completos.',
  metodologia: 'Suavizado Exponencial Ponderado · α = 0.75 · ARIMA y Regresión Lineal descartados por el panel',
}

export default function Forecast2027Page() {
  const { authFetch, isEditor } = useAuth()
  const [data,         setData]         = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [cambios,      setCambios]      = useState({})
  const [guardando,    setGuardando]    = useState(false)
  const [expanded,     setExpanded]     = useState({})
  const [filtros,         setFiltros]         = useState({ sku: '', descripcion: '', marca: [], subcategoria: [], tipo_producto: [] })
  const [filtroCategoria, setFiltroCategoria] = useState([])
  const [filtroTemp,      setFiltroTemp]      = useState([])
  const [sortBy,       setSortBy]       = useState('descripcion')
  const [sortDir,      setSortDir]      = useState('asc')
  const [eventos,      setEventos]      = useState(EVENTOS_DEFAULT)
  const [editEvento,   setEditEvento]   = useState(null)
  const [crecimiento,  setCrecimiento]  = useState(PANEL.consenso)
  const [modoFijo,     setModoFijo]     = useState(true)
  const [recalculating,setRecalculating]= useState(false)
  const [recalcResult, setRecalcResult] = useState(null)
  const [showPanel,    setShowPanel]    = useState(false)
  const [excelPeriodo, setExcelPeriodo] = useState('m9')
  const [filtroQ,      setFiltroQ]      = useState('todo')

  const PERIODOS = [
    { val: 'm0',  label: 'Ene' }, { val: 'm1',  label: 'Feb' }, { val: 'm2',  label: 'Mar' },
    { val: 'm3',  label: 'Abr' }, { val: 'm4',  label: 'May' }, { val: 'm5',  label: 'Jun' },
    { val: 'm6',  label: 'Jul' }, { val: 'm7',  label: 'Ago' }, { val: 'm8',  label: 'Sep' },
    { val: 'm9',  label: 'Oct' }, { val: 'm10', label: 'Nov' }, { val: 'm11', label: 'Dic' },
    { val: 'q1',  label: 'Q1 Ene–Mar' }, { val: 'q2', label: 'Q2 Abr–Jun' },
    { val: 'q3',  label: 'Q3 Jul–Sep' }, { val: 'q4', label: 'Q4 Oct–Dic' },
    { val: 'todo', label: 'Año completo' },
  ]

  function exportarPeriodo() {
    const p = excelPeriodo
    const meses_idx = p.startsWith('m') ? [parseInt(p.slice(1))]
      : p === 'q1' ? [0,1,2] : p === 'q2' ? [3,4,5]
      : p === 'q3' ? [6,7,8] : p === 'q4' ? [9,10,11]
      : [0,1,2,3,4,5,6,7,8,9,10,11]
    const label = PERIODOS.find(x => x.val === p)?.label || p

    const rows = filasFiltradas.map(fila => {
      const precio = fila.precio_lp || 0
      const row = {
        'SKU':          fila.sku,
        'Descripción':  fila.descripcion || '',
        'Marca':        fila.marca || '',
        'Subcategoría': fila.subcategoria || '',
        'Tipo':         fila.tipo_producto || '',
        'Temporada':    fila.temporada || '',
        'Precio LP':    precio,
        'Precio Neto':  Math.round(precio / 1.19),
      }
      meses_idx.forEach(mi => {
        const fc = fila.meses_total[mi] ?? 0
        row[`Fc ${MESES[mi]}`]  = fc
        row[`PxQ ${MESES[mi]}`] = Math.round(fc * precio)
      })
      return row
    })

    const ws = XLSX.utils.json_to_sheet(rows)
    ws['!cols'] = [
      { wch: 12 }, { wch: 40 }, { wch: 14 }, { wch: 18 }, { wch: 22 }, { wch: 12 },
      { wch: 12 }, { wch: 12 },
      ...meses_idx.flatMap(() => [{ wch: 12 }, { wch: 14 }]),
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, label)
    XLSX.writeFile(wb, `forecast_${label.toLowerCase().replace(/[^a-z0-9]/g,'_')}_2027.xlsx`)
  }

  async function recalcular() {
    setRecalculating(true)
    setRecalcResult(null)
    try {
      const body = modoFijo
        ? { crecimiento_pct: parseFloat(crecimiento) }
        : { crecimiento_pct: null }
      const res = await authFetch(`${API}/forecast-2027/recalcular`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const text = await res.text()
      let data
      try { data = JSON.parse(text) } catch { data = {} }
      if (!res.ok) {
        setRecalcResult({ ok: false, salida: `HTTP ${res.status}: ${data.detail || text}` })
        return
      }
      setRecalcResult(data)
      if (data.ok) { setCambios({}); cargar() }
    } catch (e) {
      setRecalcResult({ ok: false, salida: String(e) })
    } finally {
      setRecalculating(false)
    }
  }

  const cargar = useCallback(async () => {
    setLoading(true)
    try {
      const res = await authFetch(`${API}/forecast-2027?limit=2000`)
      setData(res.ok ? await res.json() : null)
    } catch { setData(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { cargar() }, [])

  function getVal(sku, canal, mi) {
    const key = `${sku}|${canal}|${mi+1}`
    return key in cambios ? cambios[key] : null
  }

  function setCelda(sku, canal, mi, val) {
    const key = `${sku}|${canal}|${mi+1}`
    setCambios(prev => ({ ...prev, [key]: Math.max(0, parseInt(val) || 0) }))
  }

  async function guardar() {
    if (!Object.keys(cambios).length) return
    setGuardando(true)
    const items = Object.entries(cambios).map(([key, cantidad]) => {
      const [sku, canal, mes] = key.split('|')
      return { sku, canal, mes: parseInt(mes), cantidad }
    })
    await authFetch(`${API}/forecast-2027/bulk-upsert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(items),
    })
    setCambios({})
    setGuardando(false)
    cargar()
  }

  const nCambios = Object.keys(cambios).length

  // ── Snapshots ──────────────────────────────────────────────────
  const [showSnap, setShowSnap]     = useState(false)
  const [snapNombre, setSnapNombre] = useState('')
  const [snapGuardando, setSnapGuardando] = useState(false)
  const [snapMsg, setSnapMsg]       = useState(null)

  async function guardarSnapshot() {
    if (!snapNombre.trim()) return
    setSnapGuardando(true)
    setSnapMsg(null)
    try {
      const r = await authFetch(`${API}/forecast-2027/snapshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: snapNombre.trim(), descripcion: '' }),
      })
      const d = await r.json()
      if (d.ok) {
        setSnapMsg({ tipo: 'ok', txt: `Snapshot "${snapNombre}" guardado — ${d.total_skus} SKUs, ${d.total_uds.toLocaleString('es-CL')} uds` })
        setSnapNombre('')
        setTimeout(() => { setShowSnap(false); setSnapMsg(null) }, 3000)
      } else {
        setSnapMsg({ tipo: 'err', txt: JSON.stringify(d) })
      }
    } catch (e) {
      setSnapMsg({ tipo: 'err', txt: String(e) })
    } finally {
      setSnapGuardando(false)
    }
  }

  // Opciones para dropdowns (de todas las filas disponibles)
  const todasFilas = useMemo(() => data?.filas || [], [data])
  const opMarcas        = useMemo(() => [...new Set(todasFilas.map(f => f.marca).filter(Boolean))].sort(), [todasFilas])
  const opSubcategorias = useMemo(() => [...new Set(todasFilas.map(f => f.subcategoria).filter(Boolean))].sort(), [todasFilas])
  const opTipoProductos = useMemo(() => [...new Set(todasFilas.map(f => f.tipo_producto).filter(Boolean))].sort(), [todasFilas])
  const opTemporadas    = useMemo(() => [...new Set(todasFilas.map(f => f.temporada).filter(Boolean))].sort(), [todasFilas])

  // Categorías: solo las que existen en las filas que pasan los demás filtros
  const filasSinCateg = useMemo(() => todasFilas.filter(f => {
    if (filtroTemp.length              && !filtroTemp.includes(f.temporada))              return false
    if (filtros.marca.length           && !filtros.marca.includes(f.marca))               return false
    if (filtros.subcategoria.length    && !filtros.subcategoria.includes(f.subcategoria)) return false
    if (filtros.tipo_producto.length   && !filtros.tipo_producto.includes(f.tipo_producto)) return false
    if (filtros.sku         && !f.sku.toLowerCase().includes(filtros.sku.toLowerCase()))  return false
    if (filtros.descripcion && !f.descripcion?.toLowerCase().includes(filtros.descripcion.toLowerCase())) return false
    return true
  }), [todasFilas, filtros, filtroTemp])
  const opCategorias = useMemo(() => [...new Set(filasSinCateg.map(f => f.categoria).filter(Boolean))].sort(), [filasSinCateg])

  // Filas filtradas + ordenadas
  const filasFiltradas = useMemo(() => {
    if (!data) return []
    const filtered = todasFilas.filter(f => {
      if (filtroCategoria.length       && !filtroCategoria.includes(f.categoria))         return false
      if (filtroTemp.length            && !filtroTemp.includes(f.temporada))              return false
      if (filtros.marca.length         && !filtros.marca.includes(f.marca))               return false
      if (filtros.subcategoria.length  && !filtros.subcategoria.includes(f.subcategoria)) return false
      if (filtros.tipo_producto.length && !filtros.tipo_producto.includes(f.tipo_producto)) return false
      if (filtros.sku         && !f.sku.toLowerCase().includes(filtros.sku.toLowerCase())) return false
      if (filtros.descripcion && !f.descripcion?.toLowerCase().includes(filtros.descripcion.toLowerCase())) return false
      return true
    })
    const dir = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      let va, vb
      if (sortBy === 'total_uds')       { va = a.total_uds;      vb = b.total_uds }
      else if (sortBy === 'venta_neta') { va = a.venta_neta;     vb = b.venta_neta }
      else if (sortBy === 'marca')      { va = a.marca||'';       vb = b.marca||'' }
      else if (sortBy === 'sku')        { va = a.sku;             vb = b.sku }
      else                              { va = a.descripcion||''; vb = b.descripcion||'' }
      return typeof va === 'string' ? va.localeCompare(vb) * dir : (va - vb) * dir
    })
  }, [data, filtros, filtroCategoria, filtroTemp, sortBy, sortDir])

  // Totales por mes (unidades y venta neta)
  const { totUds, totVenta, totBruta } = useMemo(() => {
    const totUds   = Array(12).fill(0)
    const totVenta = Array(12).fill(0)
    const totBruta = Array(12).fill(0)
    filasFiltradas.forEach(f => {
      const precio = f.precio_lp || 0
      ;(f.canales || []).forEach(c => {
        ;(c.meses || []).forEach((v, mi) => {
          const val = getVal(f.sku, c.canal, mi) ?? v
          totUds[mi]   += (val || 0)
          totVenta[mi] += (val || 0) * precio / 1.19
          totBruta[mi] += (val || 0) * precio
        })
      })
    })
    return { totUds, totVenta, totBruta }
  }, [filasFiltradas, cambios])

  // Meses visibles según filtroQ
  const mesVisible = mi => {
    if (filtroQ === 'todo') return true
    if (filtroQ === 'q1') return mi < 3
    if (filtroQ === 'q2') return mi >= 3 && mi < 6
    if (filtroQ === 'q3') return mi >= 6 && mi < 9
    if (filtroQ === 'q4') return mi >= 9
    return true
  }

  const totalUds   = totUds.reduce((a, b, i) => a + (mesVisible(i) ? b : 0), 0)
  const totalVenta = totVenta.reduce((a, b, i) => a + (mesVisible(i) ? b : 0), 0)

  // Meses con evento
  const mesEvento = {}
  Object.values(eventos).forEach(e => { mesEvento[e.mes - 1] = e })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Modal panel de expertos */}
      {showPanel && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', display:'flex',
          alignItems:'center', justifyContent:'center', zIndex:1000 }}
          onClick={() => setShowPanel(false)}>
          <div style={{ background:'#FFFFFF', borderRadius:12, padding:28, width:520,
            maxWidth:'95vw', boxShadow:'0 8px 40px rgba(0,0,0,0.5)', border:'1px solid #D0D0D0' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ fontWeight:700, fontSize:16, color:'#111111', marginBottom:4 }}>
              Panel de Expertos — Crecimiento 2027
            </div>
            <div style={{ fontSize:11, color:'#666666', marginBottom:18 }}>
              Convocado junio 2026 · 4 especialistas en economía, retail y estrategia
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:18 }}>
              {PANEL.expertos.map((e, i) => (
                <div key={i} style={{ background:'#F3F3F3', borderRadius:8, padding:'10px 14px',
                  border:'1px solid #D0D0D0' }}>
                  <div style={{ fontSize:10, color:'#666666', marginBottom:4 }}>{e.rol}</div>
                  <div style={{ fontSize:22, fontWeight:700, color:'#0D9488', fontFamily:'var(--mono)' }}>
                    {e.valor}%
                  </div>
                </div>
              ))}
            </div>
            <div style={{ background:'#F3F3F3', borderRadius:8, padding:'12px 16px',
              border:'1px solid #0D9488', marginBottom:14 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
                <div style={{ fontSize:11, color:'#666666' }}>Consenso del panel</div>
                <div style={{ fontSize:28, fontWeight:800, color:'#0D9488', fontFamily:'var(--mono)' }}>
                  {PANEL.consenso}%
                </div>
              </div>
              <div style={{ display:'flex', gap:16, fontSize:11 }}>
                <span style={{ color:'#f59e0b' }}>Conservador: {PANEL.conservador}%</span>
                <span style={{ color:'#666666' }}>·</span>
                <span style={{ color:'#0D9488' }}>Optimista: {PANEL.optimista}%</span>
              </div>
            </div>
            <div style={{ fontSize:12, color:'#666666', lineHeight:1.6, marginBottom:12 }}>
              {PANEL.justificacion}
            </div>
            <div style={{ background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.4)',
              borderRadius:6, padding:'8px 12px', fontSize:11, color:'#ef4444' }}>
              ⚠ {PANEL.advertencia}
            </div>
            <button onClick={() => setShowPanel(false)}
              style={{ marginTop:16, width:'100%', padding:'8px', background:'#D0D0D0',
                color:'#111111', border:'none', borderRadius:8, cursor:'pointer', fontWeight:600 }}>
              Cerrar
            </button>
          </div>
        </div>
      )}

      {/* Modal resultado recalcular */}
      {recalcResult && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', display:'flex',
          alignItems:'center', justifyContent:'center', zIndex:1000 }}
          onClick={() => setRecalcResult(null)}>
          <div style={{ background:'#FFFFFF', borderRadius:10, padding:24, width:460,
            maxWidth:'95vw', border:'1px solid #D0D0D0' }} onClick={e => e.stopPropagation()}>
            <div style={{ fontWeight:700, color: recalcResult.ok ? '#0D9488' : '#ef4444', marginBottom:12 }}>
              {recalcResult.ok ? '✓ Forecast recalculado' : '✗ Error al recalcular'}
            </div>
            <pre style={{ fontSize:11, fontFamily:'var(--mono)', whiteSpace:'pre-wrap',
              maxHeight:200, overflowY:'auto', color:'#666666', margin:0 }}>
              {recalcResult.salida}
            </pre>
            <button onClick={() => setRecalcResult(null)}
              style={{ marginTop:14, width:'100%', padding:'7px', background:'#D0D0D0',
                color:'#111111', border:'none', borderRadius:8, cursor:'pointer' }}>
              Cerrar
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', borderBottom: '1px solid #CCCCCC', background: '#F3F3F3',
        flexWrap: 'wrap', gap: 10,
      }}>
        <div>
          <div style={{ color: '#111111', fontWeight: 700, fontSize: 18 }}>Forecast 2027</div>
          <div style={{ color: '#666666', fontSize: 12, marginTop: 2 }}>
            {data ? `${filasFiltradas.length} SKUs · ${clp(totalUds)} uds · $${mclp(totalVenta)}` : 'Cargando…'}
          </div>
        </div>

        {/* Panel crecimiento */}
        <div style={{ display:'flex', alignItems:'center', gap:8, background:'#F5F5F5',
          borderRadius:10, padding:'8px 14px', border:'1px solid #D0D0D0' }}>
          <button onClick={() => setShowPanel(true)}
            title="Ver recomendación del Panel de Expertos"
            style={{ background:'none', border:'none', cursor:'pointer', padding:0,
              fontSize:11, color:'#666666', textDecoration:'underline', whiteSpace:'nowrap' }}>
            Panel IA
          </button>
          <div style={{ width:1, height:20, background:'#D0D0D0' }}/>
          <div style={{ fontSize:11, color:'#666666', whiteSpace:'nowrap' }}>Recom.</div>
          <div style={{ fontSize:16, fontWeight:800, color:'#0D9488', fontFamily:'var(--mono)',
            cursor:'pointer' }} onClick={() => setCrecimiento(PANEL.consenso)}
            title={`Usar recomendación del panel: ${PANEL.consenso}%`}>
            {PANEL.consenso}%
          </div>
          <div style={{ width:1, height:20, background:'#D0D0D0' }}/>
          <label style={{ display:'flex', alignItems:'center', gap:6, cursor:'pointer' }}>
            <input type="checkbox" checked={modoFijo} onChange={e => setModoFijo(e.target.checked)}
              style={{ accentColor:'#0D9488' }}/>
            <span style={{ fontSize:11, color:'#666666', whiteSpace:'nowrap' }}>Tasa fija</span>
          </label>
          <input
            type="number" min={0} max={100} step={0.5}
            value={crecimiento}
            onChange={e => setCrecimiento(e.target.value)}
            disabled={!modoFijo}
            style={{ width:58, textAlign:'center', fontFamily:'var(--mono)', fontWeight:700,
              fontSize:14, background:'#F3F3F3', color: modoFijo ? '#0D9488' : '#888888',
              border:`1px solid ${modoFijo ? '#0D9488' : '#D0D0D0'}`, borderRadius:6,
              padding:'3px 4px' }}
          />
          <span style={{ fontSize:11, color:'#666666' }}>%</span>
          <button onClick={recalcular} disabled={recalculating || !isEditor}
            style={{ padding:'5px 14px', borderRadius:8, fontWeight:700, fontSize:12,
              cursor: isEditor ? 'pointer' : 'default',
              background: recalculating ? '#D0D0D0' : '#0D9488',
              color:'#fff', border:'none', whiteSpace:'nowrap' }}>
            {recalculating ? <span>↻ Calculando…</span> : '↻ Recalcular'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Botones de eventos */}
          {Object.entries(eventos).map(([key, ev]) => (
            <button key={key} onClick={() => setEditEvento({ key, ...ev })}
              style={{ padding: '4px 10px', borderRadius: 8, border: `2px solid ${ev.color}`,
                background: ev.color + '33', color: ev.color === '#1E293B' ? '#fff' : ev.color,
                fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>
              {ev.label} · {MESES[ev.mes-1]}
            </button>
          ))}
          {/* Excel export */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 0, border: '1px solid #34d399', borderRadius: 6, overflow: 'hidden' }}>
            <select value={excelPeriodo} onChange={e => setExcelPeriodo(e.target.value)}
              style={{ padding: '6px 6px', fontSize: 11, background: '#E8F5EC', color: '#34d399',
                border: 'none', borderRight: '1px solid #34d399', cursor: 'pointer', outline: 'none' }}>
              <optgroup label="Mes">
                {PERIODOS.filter(p => p.val.startsWith('m')).map(p => (
                  <option key={p.val} value={p.val}>{p.label}</option>
                ))}
              </optgroup>
              <optgroup label="Quarter">
                {PERIODOS.filter(p => p.val.startsWith('q')).map(p => (
                  <option key={p.val} value={p.val}>{p.label}</option>
                ))}
              </optgroup>
              <optgroup label="Total">
                <option value="todo">Año completo</option>
              </optgroup>
            </select>
            <button onClick={exportarPeriodo}
              title={`Exportar ${filasFiltradas.length} SKUs filtrados`}
              style={{ padding: '6px 10px', fontSize: 12, fontWeight: 700,
                background: '#E8F5EC', color: '#34d399', border: 'none', cursor: 'pointer' }}>
              ⬇ Excel
            </button>
          </div>

          <button
            onClick={guardar}
            disabled={!nCambios || guardando || !isEditor}
            style={{
              padding: '6px 18px', borderRadius: 8, fontWeight: 700, fontSize: 13, cursor: 'pointer',
              background: nCambios ? '#16a34a' : '#D0D0D0', color: '#fff', border: 'none',
            }}>
            {guardando ? 'Guardando…' : nCambios ? `Guardar (${nCambios})` : 'Sin cambios'}
          </button>

          {/* Botón snapshot */}
          <button onClick={() => setShowSnap(true)} title="Guardar versión histórica del forecast actual"
            style={{ padding:'6px 12px', borderRadius:8, fontWeight:700, fontSize:12, cursor:'pointer',
              background:'#F0EBF8', color:'#a78bfa', border:'1px solid #4c3a8a' }}>
            📸 Snapshot
          </button>
        </div>
      </div>

      {/* Modal snapshot */}
      {showSnap && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.5)',
          display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000 }}
          onClick={e => { if (e.target===e.currentTarget) setShowSnap(false) }}>
          <div style={{ background:'#F5F5F5', borderRadius:10, padding:28, width:420,
            border:'1px solid #4c3a8a', boxShadow:'0 8px 32px rgba(0,0,0,0.4)' }}>
            <div style={{ fontWeight:700, fontSize:15, color:'#a78bfa', marginBottom:16 }}>
              📸 Guardar Snapshot del Forecast 2027
            </div>
            <div style={{ fontSize:12, color:'#666666', marginBottom:12 }}>
              Guarda una copia inmutable del forecast actual. Útil para comparar versiones antes/después de un recálculo.
            </div>
            <input
              value={snapNombre}
              onChange={e => setSnapNombre(e.target.value)}
              placeholder="Nombre del snapshot (ej: Pre-recalculo jun-2026)"
              style={{ width:'100%', padding:'8px 10px', borderRadius:6, fontSize:13,
                background:'#F3F3F3', color:'#111111', border:'1px solid #D0D0D0',
                outline:'none', marginBottom:12, boxSizing:'border-box' }}
              onKeyDown={e => e.key==='Enter' && guardarSnapshot()}
              autoFocus
            />
            {snapMsg && (
              <div style={{ padding:'8px 12px', borderRadius:6, marginBottom:12, fontSize:12,
                background: snapMsg.tipo==='ok' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                color: snapMsg.tipo==='ok' ? '#34d399' : '#f87171',
                border: `1px solid ${snapMsg.tipo==='ok' ? '#16a34a' : '#dc2626'}` }}>
                {snapMsg.txt}
              </div>
            )}
            <div style={{ display:'flex', gap:8, justifyContent:'flex-end' }}>
              <button onClick={() => setShowSnap(false)} className="btn btn-ghost" style={{fontSize:12}}>Cancelar</button>
              <button onClick={guardarSnapshot} disabled={!snapNombre.trim() || snapGuardando}
                style={{ padding:'6px 16px', borderRadius:6, fontWeight:700, fontSize:12,
                  background: snapNombre.trim() ? '#7c3aed' : '#D0D0D0', color:'#fff', border:'none',
                  cursor: snapNombre.trim() ? 'pointer' : 'not-allowed' }}>
                {snapGuardando ? 'Guardando…' : '📸 Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filtros top bar */}
      {(() => {
        const hayFiltros = filtroCategoria.length || filtroTemp.length || filtros.marca.length ||
          filtros.subcategoria.length || filtros.tipo_producto.length || filtros.sku || filtros.descripcion
        return (
          <div style={{ display: 'flex', gap: 10, padding: '8px 20px', background: '#F3F3F3', borderBottom: '1px solid #CCCCCC', flexWrap: 'wrap', alignItems: 'center' }}>
            <MultiSelect
              options={opCategorias}
              value={filtroCategoria}
              onChange={setFiltroCategoria}
              placeholder="Todas las categorías"
              style={{ width: 200 }}
            />
            <MultiSelect
              options={opTemporadas}
              value={filtroTemp}
              onChange={setFiltroTemp}
              placeholder="Todas las temporadas"
              style={{ width: 180 }}
            />

            <button className="btn btn-secondary btn-sm" onClick={cargar} disabled={loading}>
              {loading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : '↻'} Actualizar
            </button>

            {/* Filtro quarters */}
            <div style={{ display: 'flex', gap: 2, background: '#E8E8E8', borderRadius: 6, padding: 2 }}>
              {['todo','q1','q2','q3','q4'].map(q => (
                <button key={q} onClick={() => setFiltroQ(q)} style={{
                  padding: '4px 10px', fontSize: 11, fontWeight: 700,
                  border: 'none', borderRadius: 4, cursor: 'pointer',
                  background: filtroQ === q ? '#0D9488' : 'transparent',
                  color: filtroQ === q ? '#fff' : '#666666',
                  textTransform: 'uppercase',
                }}>{q === 'todo' ? 'Todo' : q.toUpperCase()}</button>
              ))}
            </div>

            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ background: '#FFFFFF', color: '#111111', border: '1px solid #D0D0D0', borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>
              <option value="descripcion">Ordenar: Descripción</option>
              <option value="sku">Ordenar: SKU</option>
              <option value="marca">Ordenar: Marca</option>
              <option value="total_uds">Ordenar: Total Uds</option>
              <option value="venta_neta">Ordenar: Venta Neta</option>
            </select>
            <button onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
              style={{ background: '#FFFFFF', color: '#111111', border: '1px solid #D0D0D0', borderRadius: 6, padding: '4px 10px', fontSize: 13, cursor: 'pointer' }}>
              {sortDir === 'asc' ? '↑' : '↓'}
            </button>
            {hayFiltros && (
              <button onClick={() => { setFiltros({ sku:'', descripcion:'', marca:[], subcategoria:[], tipo_producto:[] }); setFiltroCategoria([]); setFiltroTemp([]) }}
                style={{ padding: '4px 10px', fontSize: 11, background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                ✕ Limpiar filtros
              </button>
            )}
          </div>
        )
      })()}

      {/* Modal editar evento */}
      {editEvento && (
        <div className="modal-overlay" onClick={() => setEditEvento(null)}>
          <div className="modal" style={{ maxWidth: 300 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Editar {editEvento.label}</span>
              <button className="modal-close" onClick={() => setEditEvento(null)}>✕</button>
            </div>
            <div className="form-group">
              <label className="form-label">Mes del evento</label>
              <select className="form-input" value={editEvento.mes}
                onChange={e => setEditEvento(ev => ({ ...ev, mes: parseInt(e.target.value) }))}>
                {MESES.map((m, i) => <option key={i} value={i+1}>{m}</option>)}
              </select>
            </div>
            <div className="form-actions">
              <button className="btn btn-secondary" onClick={() => setEditEvento(null)}>Cancelar</button>
              <button className="btn btn-primary" onClick={() => {
                setEventos(prev => ({ ...prev, [editEvento.key]: { mes: editEvento.mes, label: editEvento.label, color: editEvento.color } }))
                setEditEvento(null)
              }}>Guardar</button>
            </div>
          </div>
        </div>
      )}

      {/* Tabla */}
      {loading ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span className="spinner"/>
        </div>
      ) : !data ? (
        <div className="empty-state"><div>Error al cargar</div></div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto' }}>
          <table style={{ borderCollapse: 'separate', borderSpacing: 0, tableLayout: 'fixed', width: 'max-content', fontSize: 12, background: '#FFFFFF' }}>
            <thead>
              {/* ── Fila 1: Grupos Q ─────────────────────────────── */}
              <tr style={{ height: 28 }}>
                {COLS.map((c, i) => (
                  <th key={c.key} style={{ ...thFijo(i), borderBottom: '1px solid #D0D0D0' }}>
                    {i === 0 ? 'Forecast 2027' : ''}
                  </th>
                ))}
                <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #2e4070', borderBottom:'1px solid #D0D0D0', letterSpacing:0.5 }}>Q1 — Ene · Feb · Mar</th>
                <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #2e4070', borderBottom:'1px solid #D0D0D0', letterSpacing:0.5 }}>Q2 — Abr · May · Jun</th>
                <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #2e4070', borderBottom:'1px solid #D0D0D0', letterSpacing:0.5 }}>Q3 — Jul · Ago · Sep</th>
                <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #2e4070', borderBottom:'1px solid #D0D0D0', letterSpacing:0.5 }}>Q4 — Oct · Nov · Dic</th>
                <th style={{ background:'#F3F3F3', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderBottom:'1px solid #D0D0D0', minWidth:90 }}>TOTAL</th>
              </tr>

              {/* ── Fila 2a: TOTAL ───────────────────────────────── */}
              <tr style={{ background: '#E8E8E8' }}>
                <th colSpan={999} style={{
                  position: 'sticky', left: 0, zIndex: 3,
                  background: '#E8E8E8', borderBottom: '1px solid #D0D0D0',
                  fontSize: 11, fontWeight: 700, padding: '5px 12px', textAlign: 'left',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ color: '#0D9488' }}>TOTAL &nbsp;</span>
                  <span style={{ color: '#666666', fontWeight: 400 }}>{clp(filasFiltradas.length)} SKUs · </span>
                  <span style={{ color: '#0D9488', fontFamily: 'var(--mono)' }}>{clp(totalUds)} uds</span>
                </th>
              </tr>

              {/* ── Fila 2b: Venta Neta ──────────────────────────── */}
              <tr style={{ background: '#D4F5F0' }}>
                <th colSpan={999} style={{
                  position: 'sticky', left: 0, zIndex: 3,
                  background: '#D4F5F0', borderBottom: '2px solid #0D9488',
                  fontSize: 11, fontWeight: 700, padding: '5px 12px', textAlign: 'left',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ color: '#666666', fontWeight: 400 }}>Venta Neta &nbsp;</span>
                  <span style={{ color: '#0D9488', fontFamily: 'var(--mono)', fontWeight: 700 }}>${mclp(totalVenta)}</span>
                </th>
              </tr>

              {/* ── Fila 3: Cabeceras mes ────────────────────────── */}
              <tr>
                {COLS.map((c, i) => (
                  <th key={c.key} style={{ ...thFijo(i), zIndex: 5, top: 0 }}>{c.label}</th>
                ))}
                {MESES.map((m, mi) => {
                  if (!mesVisible(mi)) return null
                  const ev = mesEvento[mi]
                  const isQ1 = mi % 3 === 0
                  return (
                    <th key={mi} style={{
                      background: ev ? ev.color : (isQ1 ? '#E0F2FE' : '#F3F3F3'),
                      color: '#111111', fontSize: 11, fontWeight: 700,
                      padding: '4px 4px 2px', textAlign: 'center',
                      borderRight: isQ1 && mi > 0 ? '2px solid #2e4070' : '1px solid #CCCCCC',
                      borderBottom: '2px solid #0D9488',
                      minWidth: 72, whiteSpace: 'nowrap',
                    }}>
                      {m}
                      {ev && <div style={{ fontSize: 9, opacity: 0.8, fontWeight: 400 }}>{ev.label}</div>}
                    </th>
                  )
                })}
                <th style={{ background: '#F3F3F3', color: '#0D9488', fontSize: 11, fontWeight: 700,
                  padding: '6px 8px', textAlign: 'center', borderBottom: '2px solid #0D9488', minWidth: 90 }}>TOTAL</th>
              </tr>

              {/* ── Fila 4: Filtros inline ───────────────────────── */}
              <tr style={{ background: '#F3F3F3' }}>
                <th style={{ ...thFijo(0), background: '#F3F3F3', padding: '4px 4px' }}>
                  <MultiSelect dark options={opMarcas} value={filtros.marca}
                    onChange={v => setFiltros(f => ({ ...f, marca: v }))} placeholder="▼ Marca" />
                </th>
                <th style={{ ...thFijo(1), background: '#F3F3F3', padding: '4px 4px' }}>
                  <input value={filtros.sku} onChange={e => setFiltros(f => ({ ...f, sku: e.target.value }))}
                    placeholder="Buscar…" style={{ width: '100%', fontSize: 10, background: '#D0D0D0',
                      color: filtros.sku ? '#0D9488' : '#666666', border: `1px solid ${filtros.sku ? '#0D9488' : '#D0D0D0'}`,
                      borderRadius: 3, padding: '2px 4px' }} />
                </th>
                <th style={{ ...thFijo(2), background: '#F3F3F3', padding: '4px 4px' }}>
                  <input value={filtros.descripcion} onChange={e => setFiltros(f => ({ ...f, descripcion: e.target.value }))}
                    placeholder="Buscar…" style={{ width: '100%', fontSize: 10, background: '#D0D0D0',
                      color: filtros.descripcion ? '#0D9488' : '#666666', border: `1px solid ${filtros.descripcion ? '#0D9488' : '#D0D0D0'}`,
                      borderRadius: 3, padding: '2px 4px' }} />
                </th>
                <th style={{ ...thFijo(3), background: '#F3F3F3', padding: '4px 4px' }}>
                  <MultiSelect dark options={opSubcategorias} value={filtros.subcategoria}
                    onChange={v => setFiltros(f => ({ ...f, subcategoria: v }))} placeholder="▼ Subcategoría" />
                </th>
                <th style={{ ...thFijo(4), background: '#F3F3F3', padding: '4px 4px' }}>
                  <MultiSelect dark options={opTipoProductos} value={filtros.tipo_producto}
                    onChange={v => setFiltros(f => ({ ...f, tipo_producto: v }))} placeholder="▼ Tipo de Producto" />
                </th>
                <th style={{ ...thFijo(5), background: '#F3F3F3', padding: '4px 4px', borderBottom: '2px solid #0D9488' }}>
                  <MultiSelect dark options={opTemporadas} value={filtroTemp}
                    onChange={setFiltroTemp} placeholder="▼ Temporada" />
                </th>
                {MESES.map((_, mi) => mesVisible(mi) ? (
                  <th key={mi} style={{ background: '#E8F8F6', borderRight: '1px solid #CCCCCC', borderBottom: '2px solid #0D9488', minWidth: 72, padding: '3px 4px', textAlign: 'center' }}>
                    {totBruta[mi] > 0 && <>
                      <div style={{ fontSize: 9, color: '#0D9488', fontFamily: 'var(--mono)', fontWeight: 600 }}>N: ${mclp(totVenta[mi])}</div>
                      <div style={{ fontSize: 9, color: '#6b7a99', fontFamily: 'var(--mono)', fontWeight: 600 }}>B: ${mclp(totBruta[mi])}</div>
                    </>}
                  </th>
                ) : null)}
                <th style={{ background: '#E8F8F6', borderBottom: '2px solid #0D9488', minWidth: 90, padding: '3px 6px', textAlign: 'center' }}>
                  {totalVenta > 0 && <>
                    <div style={{ fontSize: 9, color: '#0D9488', fontFamily: 'var(--mono)', fontWeight: 600 }}>N: ${mclp(totalVenta)}</div>
                    <div style={{ fontSize: 9, color: '#6b7a99', fontFamily: 'var(--mono)', fontWeight: 600 }}>B: ${mclp(totBruta.reduce((a,b,i)=>a+(mesVisible(i)?b:0),0))}</div>
                  </>}
                </th>
              </tr>
            </thead>

            <tbody>
              {filasFiltradas.map((fila, ri) => {
                const bgBase = ri % 2 === 0 ? '#F5F5F5' : '#EBEBEB'
                const isOpen = expanded[fila.sku]
                const precio = fila.precio_lp || 0

                // Totales fila SKU
                const totalFilaUds = fila.meses_total.reduce((a, b) => a + b, 0)
                const totalFilaVenta = totalFilaUds * precio

                return [
                  /* Fila SKU — expandible */
                  <tr key={fila.sku} style={{ height: 36, cursor: 'pointer' }}
                    onClick={() => setExpanded(prev => ({ ...prev, [fila.sku]: !prev[fila.sku] }))}>
                    <td style={{ ...tdFijo(0, bgBase), color: '#0D9488', fontWeight: 600 }}>
                      {fila.marca || '—'}
                    </td>
                    <td style={{ ...tdFijo(1, bgBase), color: '#0D9488', fontFamily: 'var(--mono)' }}>
                      <span style={{ marginRight: 4, fontSize: 10, color: '#888888' }}>{isOpen ? '▾' : '▸'}</span>
                      {fila.sku}
                    </td>
                    <td style={{ ...tdFijo(2, bgBase), color: '#111111' }} title={fila.descripcion}>
                      {fila.descripcion || '—'}
                    </td>
                    <td style={{ ...tdFijo(3, bgBase), color: '#666666', fontSize: 11 }} title={fila.categoria || ''}>
                      {fila.subcategoria || fila.categoria || '—'}
                    </td>
                    <td style={{ ...tdFijo(4, bgBase), color: fila.tipo_producto ? '#666666' : '#ef4444', fontSize: 11 }}>
                      {fila.tipo_producto || <em style={{opacity:0.5}}>—</em>}
                    </td>
                    <td style={{ ...tdFijo(5, bgBase), color: '#666666', fontSize: 11 }}>
                      {fila.temporada || '—'}
                    </td>

                    {fila.meses_total.map((v, mi) => {
                      if (!mesVisible(mi)) return null
                      const bruto = v * precio
                      const neto  = v * precio / 1.19
                      return (
                        <td key={mi} style={{
                          minWidth: 72, textAlign: 'center', padding: '2px 4px',
                          borderRight: '1px solid #CCCCCC', borderBottom: '1px solid #CCCCCC',
                          background: bgBase, verticalAlign: 'middle',
                        }}>
                          <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: v > 0 ? '#111111' : '#D0D0D0', fontWeight: 700 }}>
                            {v === 0 ? '-' : clp(v)}
                          </div>
                          {v > 0 && <div style={{ fontSize: 9, color: '#888888', fontFamily: 'var(--mono)', marginTop: 1 }}>${mclp(bruto)}</div>}
                        </td>
                      )
                    })}
                    <td style={{
                      minWidth: 90, textAlign: 'center', padding: '2px 8px',
                      borderBottom: '1px solid #CCCCCC', background: bgBase, verticalAlign: 'middle',
                    }}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: '#0D9488', fontWeight: 600 }}>
                        {totalFilaUds === 0 ? '—' : clp(totalFilaUds)}
                      </div>
                      {totalFilaVenta > 0 && <>
                        <div style={{ fontSize: 9, color: '#0D9488', fontFamily: 'var(--mono)', marginTop: 2 }}><span style={{ fontWeight: 700 }}>N:</span> ${mclp(totalFilaVenta / 1.19)}</div>
                        <div style={{ fontSize: 9, color: '#6b7a99', fontFamily: 'var(--mono)' }}><span style={{ fontWeight: 700 }}>B:</span> ${mclp(totalFilaVenta)}</div>
                      </>}
                    </td>
                  </tr>,

                  /* Filas canal (cuando expandido) */
                  ...(isOpen ? fila.canales
                    .filter(() => true)
                    .map(c => {
                      const totalCanalUds = c.meses.reduce((a, b) => a + b, 0)
                      return (
                        <tr key={`${fila.sku}|${c.canal}`} style={{ height: 30, background: '#E8E8E8' }}>
                          <td style={{ ...tdFijo(0, '#E8E8E8') }}/>
                          <td style={{ ...tdFijo(1, '#E8E8E8'), color: '#666666', fontSize: 11 }}>
                            <span style={{ paddingLeft: 16, color: '#3a4560' }}>◦ </span>{c.canal}
                          </td>
                          <td style={{ ...tdFijo(2, '#E8E8E8') }}/>
                          <td style={{ ...tdFijo(3, '#E8E8E8') }}/>
                          <td style={{ ...tdFijo(4, '#E8E8E8') }}/>
                          <td style={{ ...tdFijo(5, '#E8E8E8') }}/>

                          {c.meses.map((v, mi) => {
                            if (!mesVisible(mi)) return null
                            const key = `${fila.sku}|${c.canal}|${mi+1}`
                            const val = key in cambios ? cambios[key] : v
                            const changed = key in cambios
                            const pxq = val * precio / 1.19
                            return (
                              <td key={mi} style={{
                                minWidth: 60, textAlign: 'center', padding: '1px 2px',
                                borderRight: '1px solid #CCCCCC', borderBottom: '1px solid #CCCCCC',
                                background: changed ? 'rgba(255,184,77,0.12)' : '#E8E8E8',
                              }}>
                                <input
                                  type="number" min="0" value={val}
                                  onChange={e => setCelda(fila.sku, c.canal, mi, e.target.value)}
                                  disabled={!isEditor}
                                  style={{
                                    width: 54, textAlign: 'center', fontSize: 11,
                                    background: 'transparent', border: changed ? '1px solid #f59e0b' : '1px solid transparent',
                                    borderRadius: 3, color: '#111111', fontFamily: 'var(--mono)', padding: '1px 2px',
                                  }}
                                />
                                {val > 0 && <div style={{ fontSize: 8, color: '#3a4560' }}>${mclp(pxq)}</div>}
                              </td>
                            )
                          })}
                          <td style={{
                            minWidth: 90, textAlign: 'center', padding: '2px 8px',
                            borderBottom: '1px solid #CCCCCC', background: '#E8E8E8',
                            fontFamily: 'var(--mono)', fontSize: 11, color: '#888888',
                          }}>
                            {clp(c.meses.reduce((a, b, mi) => {
                              const k = `${fila.sku}|${c.canal}|${mi+1}`
                              return a + (k in cambios ? cambios[k] : b)
                            }, 0))}
                          </td>
                        </tr>
                      )
                    }) : [])
                ]
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
