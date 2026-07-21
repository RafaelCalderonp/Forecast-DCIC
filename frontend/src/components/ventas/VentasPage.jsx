import { useState, useEffect, useMemo, useRef } from "react"
import { useAuth } from "../../context/AuthContext"

const API = "/api"
const MESES = ['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

function clp(n) { return Number(n).toLocaleString("es-CL") }
function num(n) { return Number(n).toLocaleString("es-CL") }

function clpM(n) {
  const m = Number(n) / 1_000_000
  return m.toLocaleString('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'M'
}

function SyncModal({ onClose, onSyncDone, authFetch }) {
  const hoy = new Date().toISOString().split('T')[0]
  const [desde,   setDesde]   = useState('2026-01-01')
  const [hasta,   setHasta]   = useState(hoy)
  const [fuente,  setFuente]  = useState('all')
  const [resync,  setResync]  = useState(false)
  const [jobId,   setJobId]   = useState(null)
  const [agregando, setAgregando] = useState(false)
  const [agregadoMsg, setAgregadoMsg] = useState(null)
  const [job,     setJob]     = useState(null)   // sync_log row
  const [tab,     setTab]     = useState('resumen')
  const pollRef = useRef(null)

  // Polling cada 4s mientras el job esté running
  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const r = await authFetch(`${API}/ventas/sync-status/${jobId}`)
        if (!r.ok) return
        const data = await r.json()
        setJob(data)
        if (data.estado !== 'running') {
          clearInterval(pollRef.current)
          if ((data.skus_faltantes?.length || 0) > 0) setTab('faltantes')
          if (data.estado === 'done') onSyncDone?.()
        }
      } catch (_) {}
    }, 4000)
    return () => clearInterval(pollRef.current)
  }, [jobId])

  async function iniciar() {
    setJob(null)
    setJobId(null)
    setTab('resumen')
    try {
      const r = await authFetch(`${API}/ventas/sync-erp-start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ desde, hasta, fuente, resync }),
      })
      const data = await r.json()
      if (data.job_id) setJobId(data.job_id)
      else setJob({ estado: 'error', error_msg: JSON.stringify(data) })
    } catch (e) {
      setJob({ estado: 'error', error_msg: String(e) })
    }
  }

  async function agregarSkus() {
    if (!faltantes.length) return
    setAgregando(true)
    setAgregadoMsg(null)
    try {
      const res = await authFetch(`${API}/ventas/agregar-skus-productos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skus: faltantes.map(f => f.sku) })
      })
      const data = await res.json()
      setAgregadoMsg(`✓ ${data.total_creados} SKUs creados en productos`)
    } catch (e) {
      setAgregadoMsg('✗ Error al agregar SKUs')
    } finally {
      setAgregando(false)
    }
  }

  function descargarCSV() {
    const faltantes = job?.skus_faltantes || []
    if (!faltantes.length) return
    const cols = ['sku','descripcion','categoria','marca','canal','n_ventas','venta_bruta']
    const csv = [cols.join(';'),
      ...faltantes.map(r => cols.map(c => String(r[c] ?? '').replace(/;/g,',')).join(';'))
    ].join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `skus_faltantes_${hoy}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const running   = jobId && job?.estado === 'running'
  const done      = job?.estado === 'done'
  const error     = job?.estado === 'error'
  const faltantes = job?.skus_faltantes || []
  const canales   = job?.canales_api ? Object.entries(job.canales_api)
    .sort((a,b) => b[1]-a[1]) : []

  // Elapsed timer
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!running) { setElapsed(0); return }
    const t = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(t)
  }, [running])

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
    }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div style={{
        background: 'var(--surface)', borderRadius: 10, padding: 28,
        width: 720, maxWidth: '96vw', maxHeight: '90vh',
        display: 'flex', flexDirection: 'column', gap: 16,
        boxShadow: '0 8px 32px rgba(0,0,0,0.28)'
      }}>

        {/* Header */}
        <div style={{ fontWeight: 700, fontSize: 16 }}>↻ Sincronizar ERP externo</div>

        {/* Parámetros */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
          {[['Desde', desde, setDesde, 'date'], ['Hasta', hasta, setHasta, 'date']].map(([label, val, set, type]) => (
            <div key={label} className="form-group">
              <label className="form-label">{label}</label>
              <input type={type} className="form-input" value={val}
                onChange={e => set(e.target.value)} disabled={running} />
            </div>
          ))}
          <div className="form-group">
            <label className="form-label">Fuente</label>
            <select className="form-input" value={fuente} onChange={e => setFuente(e.target.value)} disabled={running}>
              <option value="all">Bsale + Wivo</option>
              <option value="bsale">Solo Bsale</option>
              <option value="wivo">Solo Wivo</option>
            </select>
          </div>
        </div>

        {/* Modo resync */}
        <label style={{ display:'flex', alignItems:'center', gap:10, cursor: running ? 'not-allowed' : 'pointer',
          background:'rgba(239,68,68,0.06)', border:'1px solid rgba(239,68,68,0.25)',
          borderRadius:8, padding:'10px 14px', fontSize:13 }}>
          <input type="checkbox" checked={resync} onChange={e => setResync(e.target.checked)}
            disabled={running} style={{ width:16, height:16, cursor:'pointer' }} />
          <div>
            <span style={{ fontWeight:600, color: resync ? 'var(--danger)' : 'var(--text)' }}>
              Resincronizar — borrar y recrear el período
            </span>
            <span style={{ color:'var(--text2)', marginLeft:8, fontSize:12 }}>
              Elimina todos los registros del período seleccionado y los reinserta desde cero
            </span>
          </div>
        </label>

        {/* Progreso en background */}
        {running && (
          <div style={{
            background: 'rgba(59,130,246,0.08)', border: '1px solid var(--accent)',
            borderRadius: 8, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14
          }}>
            <span className="spinner" />
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>Sincronizando en segundo plano…</div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>
                Puedes usar la app mientras esto corre. Tiempo: {elapsed}s
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ background:'rgba(239,68,68,0.08)', border:'1px solid var(--danger)',
            borderRadius:8, padding:'12px 16px', color:'var(--danger)', fontSize:13 }}>
            ✗ Error: {job.error_msg}
          </div>
        )}

        {/* Resultado */}
        {done && (
          <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column', gap:10 }}>

            {/* KPIs */}
            <div style={{ background:'rgba(34,197,94,0.08)', border:'1px solid var(--accent2)',
              borderRadius:8, padding:'12px 18px' }}>
              <div style={{ fontWeight:600, color:'var(--accent2)', marginBottom:8 }}>
                ✓ Completado en {job.duracion_seg}s — {(job.filas_api||0).toLocaleString('es-CL')} filas recibidas de la API
              </div>
              <div style={{ display:'flex', gap:20, flexWrap:'wrap', fontSize:13 }}>
                <span><b style={{color:'var(--accent2)'}}>{(job.insertados||0).toLocaleString('es-CL')}</b> insertados</span>
                <span><b>{(job.actualizados||0).toLocaleString('es-CL')}</b> actualizados</span>
                <span><b>{(job.omitidos||0).toLocaleString('es-CL')}</b> omitidos</span>
                <span style={{color:'var(--warn)'}}>
                  <b>{(job.errores_fk||0).toLocaleString('es-CL')}</b> SKUs sin catálogo
                </span>
                <span style={{color:'var(--text2)'}}>
                  <b>{job.meses_procesados}</b> meses · <b>{job.fuente}</b>
                </span>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display:'flex', gap:8, alignItems:'center' }}>
              <div style={{ display:'flex', borderRadius:6, overflow:'hidden', border:'1px solid var(--border)' }}>
                {[
                  ['resumen', 'Canales API'],
                  ['faltantes', `SKUs a agregar (${faltantes.length})`],
                ].map(([t, label]) => (
                  <button key={t} onClick={() => setTab(t)} style={{
                    padding:'4px 14px', fontSize:12, cursor:'pointer', border:'none',
                    background: tab===t ? 'var(--accent)' : 'transparent',
                    color: tab===t ? '#fff' : 'var(--text)', fontWeight: tab===t ? 600 : 400,
                  }}>{label}</button>
                ))}
              </div>
              {tab === 'faltantes' && faltantes.length > 0 && (
                <>
                  <button className="btn btn-ghost" style={{ fontSize:12, padding:'4px 12px' }}
                    onClick={descargarCSV}>↓ CSV</button>
                  <button className="btn btn-primary" style={{ fontSize:12, padding:'4px 12px' }}
                    onClick={agregarSkus} disabled={agregando}>
                    {agregando ? 'Agregando…' : `+ Agregar ${faltantes.length} a Productos`}
                  </button>
                  {agregadoMsg && (
                    <span style={{ fontSize:12, color: agregadoMsg.startsWith('✓') ? 'var(--accent2)' : 'var(--danger)' }}>
                      {agregadoMsg}
                    </span>
                  )}
                </>
              )}
            </div>

            {/* Tabla canales API */}
            {tab === 'resumen' && canales.length > 0 && (
              <div style={{ overflowY:'auto', flex:1, borderRadius:6, border:'1px solid var(--border)' }}>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                  <thead>
                    <tr style={{ background:'var(--surface2)', position:'sticky', top:0 }}>
                      <th style={{ padding:'6px 12px', textAlign:'left', fontWeight:600, borderBottom:'1px solid var(--border)' }}>Canal (desde API)</th>
                      <th style={{ padding:'6px 12px', textAlign:'right', fontWeight:600, borderBottom:'1px solid var(--border)' }}>Venta Bruta recibida</th>
                    </tr>
                  </thead>
                  <tbody>
                    {canales.map(([canal, bruta], i) => (
                      <tr key={canal} style={{ background: i%2===0 ? 'transparent' : 'var(--surface2)' }}>
                        <td style={{ padding:'5px 12px' }}>{canal}</td>
                        <td style={{ padding:'5px 12px', textAlign:'right', fontFamily:'var(--mono)', fontWeight:600 }}>
                          ${Number(bruta).toLocaleString('es-CL', {maximumFractionDigits:0})}
                        </td>
                      </tr>
                    ))}
                    <tr style={{ background:'var(--surface2)', fontWeight:700, borderTop:'2px solid var(--border)' }}>
                      <td style={{ padding:'6px 12px' }}>TOTAL API</td>
                      <td style={{ padding:'6px 12px', textAlign:'right', fontFamily:'var(--mono)' }}>
                        ${canales.reduce((s,[,v])=>s+v,0).toLocaleString('es-CL',{maximumFractionDigits:0})}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {/* Tabla SKUs faltantes */}
            {tab === 'faltantes' && (
              <div style={{ overflowY:'auto', flex:1, borderRadius:6, border:'1px solid var(--border)' }}>
                {faltantes.length === 0
                  ? <div style={{ padding:24, textAlign:'center', color:'var(--text2)', fontSize:13 }}>
                      Sin SKUs faltantes — todos los SKUs de la API existen en el catálogo ✓
                    </div>
                  : <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                      <thead>
                        <tr style={{ background:'var(--surface2)', position:'sticky', top:0 }}>
                          {['SKU','Descripción','Marca','Categoría','Canal','Ventas','Bruta'].map(h => (
                            <th key={h} style={{ padding:'6px 10px', textAlign:'left', fontWeight:600,
                              fontSize:11, whiteSpace:'nowrap', borderBottom:'1px solid var(--border)' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {faltantes.map((f, i) => (
                          <tr key={f.sku} style={{ background: i%2===0 ? 'transparent' : 'var(--surface2)' }}>
                            <td style={{ padding:'5px 10px', fontFamily:'var(--mono)', fontWeight:600, color:'var(--warn)' }}>{f.sku}</td>
                            <td style={{ padding:'5px 10px', maxWidth:160, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.descripcion||'—'}</td>
                            <td style={{ padding:'5px 10px' }}>{f.marca||'—'}</td>
                            <td style={{ padding:'5px 10px' }}>{f.categoria||'—'}</td>
                            <td style={{ padding:'5px 10px', fontSize:11, color:'var(--text2)' }}>{f.canal||'—'}</td>
                            <td style={{ padding:'5px 10px', textAlign:'right', fontFamily:'var(--mono)' }}>{f.n_ventas}</td>
                            <td style={{ padding:'5px 10px', textAlign:'right', fontFamily:'var(--mono)', fontWeight:600 }}>
                              ${Number(f.venta_bruta).toLocaleString('es-CL',{maximumFractionDigits:0})}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                }
              </div>
            )}
          </div>
        )}

        {/* Botones */}
        <div style={{ display:'flex', gap:10, justifyContent:'flex-end', alignItems:'center', paddingTop:4 }}>
          {running && (
            <span style={{ fontSize:11, color:'var(--text2)', marginRight:'auto' }}>
              El sync continúa aunque cierres este panel.
            </span>
          )}
          <button className="btn btn-ghost" onClick={onClose}>Cerrar</button>
          <button className="btn btn-primary" onClick={iniciar} disabled={running}>
            {running ? <><span className="spinner" style={{marginRight:6}}/> Corriendo…</> : '↻ Sincronizar ERP'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function VentasPage() {
  const { authFetch } = useAuth()
  const [filas,      setFilas]      = useState([])
  const [canales,    setCanales]    = useState([])
  const [anios,      setAnios]      = useState([])
  const [loading,    setLoading]    = useState(false)
  const [filtros,    setFiltros]    = useState({ anio: 2025, mes: '', sku: '', canal: '' })
  const [showSync,   setShowSync]   = useState(false)

  useEffect(() => {
    authFetch(`${API}/ventas/canales`).then(r => r.ok ? r.json() : []).then(setCanales).catch(() => {})
    authFetch(`${API}/ventas/anios`).then(r => r.ok ? r.json() : []).then(setAnios).catch(() => {})
    cargar()
  }, [])

  async function cargar(f = filtros) {
    setLoading(true)
    const qs = new URLSearchParams()
    if (f.anio)  qs.set('anio',  f.anio)
    if (f.mes)   qs.set('mes',   f.mes)
    if (f.sku)   qs.set('sku',   f.sku)
    if (f.canal) qs.set('canal', f.canal)
    try {
      const data = await authFetch(`${API}/ventas/resumen?${qs}`).then(r => r.ok ? r.json() : [])
      setFilas(data)
    } catch (e) { setFilas([]) }
    finally { setLoading(false) }
  }

  function setFiltro(k, v) {
    const nuevo = { ...filtros, [k]: v }
    setFiltros(nuevo)
  }

  function aplicar() { cargar(filtros) }

  const totales = useMemo(() => ({
    cantidad:    filas.reduce((s, r) => s + Number(r.cantidad_neta), 0),
    venta_bruta: filas.reduce((s, r) => s + Number(r.venta_bruta_total), 0),
    venta_neta:  filas.reduce((s, r) => s + Number(r.venta_neta_total), 0),
    margen:      filas.reduce((s, r) => s + Number(r.margen_total), 0),
  }), [filas])

  const margenPct = totales.venta_neta > 0
    ? ((totales.margen / totales.venta_neta) * 100).toFixed(1)
    : 0

  return (
    <div>
      {showSync && <SyncModal onClose={() => { setShowSync(false); cargar() }} onSyncDone={() => authFetch(`${API}/ventas/anios`).then(r => r.ok ? r.json() : []).then(setAnios).catch(() => {})} authFetch={authFetch} />}

      <div className="page-header">
        <div>
          <div className="page-title">Ventas</div>
          <div className="page-subtitle">{filas.length} líneas — {num(totales.cantidad)} unidades</div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => setShowSync(true)} title="Actualizar ventas desde API">
            ↻ Sincronizar API
          </button>
        </div>
      </div>

      <div className="page-body">
        {/* KPIs */}
        <div className="stats-row" style={{ marginBottom: 20 }}>
          <div className="stat-card">
            <div className="stat-value">{num(totales.cantidad)}</div>
            <div className="stat-label">Unidades vendidas</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">${clp(totales.venta_bruta)}</div>
            <div className="stat-label">Venta bruta (c/IVA)</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">${clp(totales.venta_neta)}</div>
            <div className="stat-label">Venta neta (s/IVA)</div>
          </div>
          <div className="stat-card" style={{ borderColor: totales.margen > 0 ? 'var(--accent2)' : 'var(--border)' }}>
            <div className="stat-value" style={{ color: 'var(--accent2)' }}>${clp(totales.margen)}</div>
            <div className="stat-label">Margen total</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: margenPct >= 30 ? 'var(--accent2)' : margenPct >= 15 ? 'var(--warn)' : 'var(--danger)' }}>
              {margenPct}%
            </div>
            <div className="stat-label">Margen % (s/IVA)</div>
          </div>
        </div>

        {/* Filtros */}
        <div className="card" style={{ padding: '14px 20px', marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="form-group" style={{ minWidth: 100 }}>
              <label className="form-label">Año</label>
              <select className="form-input" value={filtros.anio} onChange={e => setFiltro('anio', e.target.value)}>
                <option value="">Todos</option>
                {anios.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ minWidth: 120 }}>
              <label className="form-label">Mes</label>
              <select className="form-input" value={filtros.mes} onChange={e => setFiltro('mes', e.target.value)}>
                <option value="">Todos</option>
                {MESES.slice(1).map((m,i) => <option key={i+1} value={i+1}>{m}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ minWidth: 160 }}>
              <label className="form-label">Canal</label>
              <select className="form-input" value={filtros.canal} onChange={e => setFiltro('canal', e.target.value)}>
                <option value="">Todos los canales</option>
                {canales.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ minWidth: 160 }}>
              <label className="form-label">SKU / Descripción</label>
              <input className="form-input" placeholder="Buscar…" value={filtros.sku}
                onChange={e => setFiltro('sku', e.target.value)}
                onKeyDown={e => e.key === 'Enter' && aplicar()} />
            </div>
            <button className="btn btn-primary" onClick={aplicar} disabled={loading}>
              {loading ? <span className="spinner"/> : "Buscar"}
            </button>
          </div>
        </div>

        {/* Tabla */}
        <div className="card" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center' }}><span className="spinner"/></div>
          ) : filas.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">⊡</div>
              <div>Sin resultados para los filtros seleccionados</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Descripción</th>
                    <th>Marca</th>
                    <th>Canal</th>
                    <th style={{ textAlign: 'center' }}>Año</th>
                    <th style={{ textAlign: 'center' }}>Mes</th>
                    <th style={{ textAlign: 'right' }}>Cant. Neta</th>
                    <th style={{ textAlign: 'right' }}>Venta Bruta</th>
                    <th style={{ textAlign: 'right' }}>Venta Neta</th>
                    <th style={{ textAlign: 'right' }}>Margen $</th>
                    <th style={{ textAlign: 'right' }}>Margen %</th>
                  </tr>
                </thead>
                <tbody>
                  {filas.map((r, i) => (
                    <tr key={i}>
                      <td><span className="td-mono">{r.sku}</span></td>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12, color: 'var(--text2)' }}>
                        {r.descripcion || '—'}
                      </td>
                      <td><span className="badge badge-blue">{r.marca || '—'}</span></td>
                      <td style={{ fontSize: 11, color: 'var(--text2)' }}>{r.canal || '—'}</td>
                      <td style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12 }}>{r.anio}</td>
                      <td style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12 }}>{MESES[r.mes]}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{num(r.cantidad_neta)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600 }}>${clp(r.venta_bruta_total)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--text2)' }}>${clp(r.venta_neta_total)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--accent2)' }}>${clp(r.margen_total)}</td>
                      <td style={{ textAlign: 'right', fontWeight: 600,
                        color: r.margen_pct >= 30 ? 'var(--accent2)' : r.margen_pct >= 15 ? 'var(--warn)' : 'var(--danger)' }}>
                        {r.margen_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ fontWeight: 700, background: 'var(--surface2)' }}>
                    <td colSpan={6} style={{ padding: '6px 8px', fontSize: 12 }}>TOTAL ({filas.length} líneas)</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', padding: '6px 8px' }}>{num(totales.cantidad)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', padding: '6px 8px', fontWeight: 700 }}>${clp(totales.venta_bruta)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', padding: '6px 8px', color: 'var(--text2)' }}>${clp(totales.venta_neta)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', padding: '6px 8px', color: 'var(--accent2)' }}>${clp(totales.margen)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, padding: '6px 8px',
                      color: margenPct >= 30 ? 'var(--accent2)' : margenPct >= 15 ? 'var(--warn)' : 'var(--danger)' }}>
                      {margenPct}%
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
