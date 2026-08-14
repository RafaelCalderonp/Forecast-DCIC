import React from "react"
import { useAuth } from "../../context/AuthContext"
import StockAnalisisModal from "./StockAnalisisModal"
import MultiSelect from "../ui/MultiSelect"
import { useForecastTabla } from './hooks/useForecastTabla'
import { clp, mclp, COLS_FIJAS, LEFT_OFFSETS, TOTAL_FROZEN, Q4_MESES, MESES, ANIO, PERIODOS, MESES_Q } from './utils/forecastUtils'

export default function TablaForecast({ anio = ANIO }) {
  const { isAdmin } = useAuth()
  const {
    // State de datos
    filas, loading, guardando, msg, temporadas,

    // Filtros globales
    filtroTemp, setFiltroTemp,
    filtroCategoria, setFiltroCategoria,
    filtros, setFiltro, limpiarFiltros,
    hayFiltros,

    // Tarjetas KPI clickeables
    filtroCard, setFiltroCard,
    conteosCard,

    // Proyección Q4
    proyeccionQ4, cambiosQ4Proy, setCambiosQ4Proy,
    guardandoQ4Proy,
    getQ4, guardarQ4Proy,

    // Toggle comparar vs 2025
    vs2025, setVs2025,

    // Filtro de quarter
    filtroQ, setFiltroQ,
    mesVisible, q1vis, q2vis, q3vis, q4vis,

    // Ordenamiento
    sortCol, setSortCol,
    sortBy, setSortBy,
    sortDir, setSortDir,

    // Filtros de columna (popover)
    colFilters,
    filterPopover, setFilterPopover,
    filterInput, setFilterInput,
    openFilter, applyFilter, toggleSort,

    // Modal stock
    skuStockModal, setSkuStockModal,

    // Edición de celdas
    editando, setEditando,
    valEdit, setValEdit,
    inputRef,
    getVal, startEdit, commitEdit, handleKeyDown,

    // Acciones
    cargar, guardar, descartar,
    cambios,

    // Filas derivadas
    filasFiltradas, filasSorted,
    opMarcas, opCategorias, opSubcategorias, opTipoProductos,

    // Totales
    totalesPorMes, totalesQ4Proy,
    ventaNetaPorMes, totalPxQ, totalVentaNeta,
    ventaNetaProyQ4, totalNetoPrQ4,
    netoQSeleccionado, totalUnits,
    nCambios, nCambiosQ4Proy,

    // Excel
    excelPeriodo, setExcelPeriodo, exportarPeriodo,
  } = useForecastTabla(anio)

  // ── Estilos comunes ──────────────────────────────────────────────────────
  const thFijo = (i) => ({
    position: 'sticky',
    left: LEFT_OFFSETS[i],
    zIndex: 4,
    background: '#DEDEDE',
    minWidth: COLS_FIJAS[i].w,
    maxWidth: COLS_FIJAS[i].w,
    padding: '6px 8px',
    borderRight: i === COLS_FIJAS.length - 1 ? '2px solid #0D9488' : '1px solid #CCCCCC',
    borderBottom: '1px solid #CCCCCC',
    fontSize: 11,
    color: '#333333',
    fontWeight: 700,
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    whiteSpace: 'nowrap',
    textAlign: i >= 5 ? 'right' : 'left',
  })

  const tdFijo = (i, bg = '#F5F5F5') => ({
    position: 'sticky',
    left: LEFT_OFFSETS[i],
    zIndex: 2,
    background: bg,
    minWidth: COLS_FIJAS[i].w,
    maxWidth: COLS_FIJAS[i].w,
    padding: '5px 8px',
    borderRight: i === COLS_FIJAS.length - 1 ? '2px solid #0F766E' : '1px solid #DDDDDD',
    borderBottom: '1px solid #DDDDDD',
    fontSize: 12,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    textAlign: i >= 5 ? 'right' : 'left',
  })

  const thMes = (highlight) => ({
    background: highlight ? '#E0F2FE' : '#DEDEDE',
    padding: '6px 4px',
    borderRight: '1px solid #CCCCCC',
    borderBottom: '1px solid #CCCCCC',
    fontSize: 10,
    color: '#333333',
    fontWeight: 600,
    textAlign: 'center',
    whiteSpace: 'nowrap',
    minWidth: 60,
  })

  // ── Popover filtro Excel ─────────────────────────────────────────────────
  const FilterPopover = filterPopover && (() => {
    const { key } = filterPopover
    const isProy = typeof key === 'string' && key.startsWith('p')
    const mesIdx = isProy ? parseInt(key.slice(1)) : key
    const label  = isProy ? `⬡ Proy. ${MESES[mesIdx]}` : MESES[mesIdx]
    const f = colFilters[key]
    const hasFilter = !!f
    return (
      <div
        onClick={e => e.stopPropagation()}
        style={{
          position: 'fixed', top: filterPopover.y, left: filterPopover.x,
          zIndex: 9999, width: 210,
          background: '#EBEBEB', border: '1px solid #3d7eff',
          borderRadius: 8, boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          padding: 12, fontSize: 12, color: '#111111',
        }}>
        <div style={{ fontWeight: 700, color: '#14B8A6', marginBottom: 8, fontSize: 11 }}>
          {label} — Filtro
        </div>

        {/* Sort */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
          <button onClick={() => toggleSort(key, 'desc')} style={{
            flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer', borderRadius: 5,
            background: sortCol?.key === key && sortCol.dir === 'desc' ? '#0D9488' : '#DEDEDE',
            color: '#111111', border: '1px solid #2a3348', fontWeight: 700,
          }}>↓ Mayor primero</button>
          <button onClick={() => toggleSort(key, 'asc')} style={{
            flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer', borderRadius: 5,
            background: sortCol?.key === key && sortCol.dir === 'asc' ? '#0D9488' : '#DEDEDE',
            color: '#111111', border: '1px solid #2a3348', fontWeight: 700,
          }}>↑ Menor primero</button>
        </div>

        <div style={{ borderTop: '1px solid #2a3348', margin: '8px 0' }} />

        {/* Filtros rápidos */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: '#666666', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>Filtro rápido</div>
          <button onClick={() => applyFilter(key, 'nozero', 0)} style={{
            width: '100%', padding: '5px 8px', textAlign: 'left', cursor: 'pointer',
            background: f?.tipo === 'nozero' ? 'rgba(61,127,255,0.2)' : 'transparent',
            color: f?.tipo === 'nozero' ? '#14B8A6' : '#111111',
            border: '1px solid ' + (f?.tipo === 'nozero' ? '#0D9488' : '#CCCCCC'),
            borderRadius: 5, fontSize: 11, marginBottom: 4,
          }}>≠ 0 — Ocultar ceros</button>
        </div>

        {/* Mayor que */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: '#666666', fontSize: 10, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Mayor que</div>
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              type="number" min={0} placeholder="Ej: 100"
              value={filterInput.gt}
              onChange={e => setFilterInput(p => ({ ...p, gt: e.target.value }))}
              style={{ flex: 1, padding: '4px 6px', background: '#DEDEDE', color: '#111111',
                border: '1px solid #2a3348', borderRadius: 5, fontSize: 11 }}
            />
            <button onClick={() => applyFilter(key, 'gt', filterInput.gt)} style={{
              padding: '4px 10px', background: '#0D9488', color: '#fff', border: 'none',
              borderRadius: 5, cursor: 'pointer', fontWeight: 700, fontSize: 11,
            }}>OK</button>
          </div>
        </div>

        {/* Menor que */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ color: '#666666', fontSize: 10, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>Menor que</div>
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              type="number" min={0} placeholder="Ej: 500"
              value={filterInput.lt}
              onChange={e => setFilterInput(p => ({ ...p, lt: e.target.value }))}
              style={{ flex: 1, padding: '4px 6px', background: '#DEDEDE', color: '#111111',
                border: '1px solid #2a3348', borderRadius: 5, fontSize: 11 }}
            />
            <button onClick={() => applyFilter(key, 'lt', filterInput.lt)} style={{
              padding: '4px 10px', background: '#0D9488', color: '#fff', border: 'none',
              borderRadius: 5, cursor: 'pointer', fontWeight: 700, fontSize: 11,
            }}>OK</button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          {hasFilter && (
            <button onClick={() => applyFilter(key, null, 0)} style={{
              flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer', borderRadius: 5,
              background: 'transparent', color: '#ef4444', border: '1px solid #ef4444',
            }}>âœ• Limpiar filtro</button>
          )}
          <button onClick={() => setFilterPopover(null)} style={{
            flex: 1, padding: '5px 0', fontSize: 11, cursor: 'pointer', borderRadius: 5,
            background: '#DEDEDE', color: '#666666', border: '1px solid #2a3348',
          }}>Cerrar</button>
        </div>
      </div>
    )
  })()

  return (
    <>
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}
      onClick={() => setFilterPopover(null)}>

      {/* ── Tarjetas KPI (clic filtra la tabla) ────────────────────── */}
      <div className="stats-row" style={{ padding: '10px 20px 0' }}>
        <div className="stat-card" style={{ cursor: 'pointer', outline: filtroCard === null ? '2px solid #3b82f6' : 'none' }}
          onClick={() => setFiltroCard(null)}>
          <div className="stat-value">{conteosCard.total}</div>
          <div className="stat-label">Total productos</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{conteosCard.marcas}</div>
          <div className="stat-label">Marcas</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{conteosCard.categorias}</div>
          <div className="stat-label">Categorías</div>
        </div>
        <div className="stat-card" style={{ cursor: 'pointer', outline: filtroCard === 'activos' ? '2px solid #22c55e' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'activos' ? null : 'activos')}>
          <div className="stat-value">{conteosCard.activos}</div>
          <div className="stat-label">Activos</div>
        </div>
        <div className="stat-card" style={{ borderColor: '#64748b', cursor: 'pointer', outline: filtroCard === 'inactivos' ? '2px solid #64748b' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'inactivos' ? null : 'inactivos')}>
          <div className="stat-value" style={{ color: '#64748b' }}>{conteosCard.inactivos}</div>
          <div className="stat-label">Inactivos</div>
        </div>
        <div className="stat-card" style={{ borderColor: '#f59e0b', cursor: 'pointer', outline: filtroCard === 'discontinuar' ? '2px solid #f59e0b' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'discontinuar' ? null : 'discontinuar')}>
          <div className="stat-value" style={{ color: '#f59e0b' }}>{conteosCard.discontinuar}</div>
          <div className="stat-label">Por discontinuar</div>
        </div>
        <div className="stat-card" style={{ borderColor: '#10b981', cursor: 'pointer', outline: filtroCard === 'nuevo' ? '2px solid #10b981' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'nuevo' ? null : 'nuevo')}>
          <div className="stat-value" style={{ color: '#10b981' }}>{conteosCard.nuevo}</div>
          <div className="stat-label">Nuevo</div>
        </div>
        <div className="stat-card" style={{ borderColor: '#6366f1', cursor: 'pointer', outline: filtroCard === 'ver_comportamiento' ? '2px solid #6366f1' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'ver_comportamiento' ? null : 'ver_comportamiento')}>
          <div className="stat-value" style={{ color: '#6366f1' }}>{conteosCard.ver_comportamiento}</div>
          <div className="stat-label">Ver comportamiento</div>
        </div>
        <div className="stat-card" style={{ borderColor: '#ef4444', cursor: 'pointer', outline: filtroCard === 'completar' ? '2px solid #ef4444' : 'none' }}
          onClick={() => setFiltroCard(f => f === 'completar' ? null : 'completar')}>
          <div className="stat-value" style={{ color: '#ef4444' }}>{conteosCard.completar}</div>
          <div className="stat-label">Por completar</div>
        </div>
      </div>

      {/* ── Barra superior ──────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 20px', borderBottom: '1px solid #2a3348',
        background: '#F5F5F5', flexShrink: 0
      }}>
        {/* Filtro Cat. Principal */}
        <MultiSelect
          options={opCategorias}
          value={filtroCategoria}
          onChange={setFiltroCategoria}
          placeholder="Todas las categorías"
          style={{ width: 200 }}
        />

        {/* Filtro temporada */}
        <MultiSelect
          options={temporadas.map(t => t.nombre)}
          value={filtroTemp}
          onChange={setFiltroTemp}
          placeholder="Todas las temporadas"
          style={{ width: 180 }}
        />

        <button className="btn btn-secondary btn-sm" onClick={cargar} disabled={loading}>
          {loading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : '↻'} Actualizar
        </button>

        {/* Filtro de quarters */}
        <div style={{ display: 'flex', gap: 2, background: '#DEDEDE', borderRadius: 6, padding: 2 }}>
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

        {/* Ordenar por campo de texto */}
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}
          style={{ background: '#F5F5F5', color: '#111111', border: '1px solid #2a3348', borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>
          <option value="descripcion">Ordenar: Descripción</option>
          <option value="sku">Ordenar: SKU</option>
          <option value="marca">Ordenar: Marca</option>
        </select>
        <button onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
          style={{ background: '#F5F5F5', color: '#111111', border: '1px solid #2a3348', borderRadius: 6, padding: '4px 10px', fontSize: 13, cursor: 'pointer' }}>
          {sortDir === 'asc' ? '↑' : '↓'}
        </button>

        {/* Toggle vs 2025 */}
        <button onClick={() => setVs2025(v => !v)} style={{
          padding: '4px 12px', fontSize: 11, fontWeight: 700,
          border: `1px solid ${vs2025 ? '#f59e0b' : '#CCCCCC'}`,
          borderRadius: 6, cursor: 'pointer',
          background: vs2025 ? 'rgba(245,158,11,0.15)' : 'transparent',
          color: vs2025 ? '#f59e0b' : '#666666',
        }}>
          {vs2025 ? '▼ vs 2025' : '◎ vs 2025'}
        </button>

        <div style={{ flex: 1 }} />

        {/* Stats rápidos */}
        <span style={{ fontSize: 12, color: '#666666' }}>
          <span style={{ color: '#111111', fontWeight: 600 }}>{filasFiltradas.length}</span>
          {hayFiltros && <span style={{ color: '#ffb84d' }}> / {filas.length}</span>} SKUs ·&nbsp;
          <span style={{ color: '#111111', fontWeight: 600 }}>{clp(totalUnits)}</span> uds ·&nbsp;
          <span style={{ color: '#0D9488', fontWeight: 600 }}>${mclp(totalPxQ)}</span>
        </span>
        {/* Neto del quarter seleccionado */}
        {netoQSeleccionado && (
          <span style={{
            fontSize: 12, padding: '4px 10px', borderRadius: 6,
            background: '#F5F0FF', border: '1px solid #4c3a8a',
            color: '#666666', display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ color: '#a78bfa', fontWeight: 700 }}>{netoQSeleccionado.label}</span>
            <span>Fc: <span style={{ color: '#0D9488', fontWeight: 700 }}>${mclp(netoQSeleccionado.fcNeto)}</span></span>
            {netoQSeleccionado.proyNeto > 0 && (
              <span>⬡ Proy: <span style={{ color: '#a78bfa', fontWeight: 700 }}>${mclp(netoQSeleccionado.proyNeto)}</span></span>
            )}
          </span>
        )}
        {hayFiltros && (
          <button onClick={limpiarFiltros}
            style={{ padding:'4px 10px', fontSize:11, background:'#7c3aed', color:'#fff', border:'none', borderRadius:4, cursor:'pointer' }}>
            âœ• Limpiar filtros
          </button>
        )}

        {nCambiosQ4Proy > 0 && (
          <span style={{ fontSize: 12, color: '#a78bfa', fontWeight: 600 }}>
            ⬡ {nCambiosQ4Proy} proy. sin guardar
          </span>
        )}
        {nCambiosQ4Proy > 0 && (
          <button onClick={guardarQ4Proy} disabled={guardandoQ4Proy}
            style={{ padding: '6px 14px', fontSize: 12, fontWeight: 700,
              background: '#EDE9FE', color: '#c4b5fd',
              border: '2px solid #7c3aed', borderRadius: 6, cursor: 'pointer' }}>
            {guardandoQ4Proy ? '…' : '⬡ Guardar Proy.'}
          </button>
        )}
        {nCambios > 0 && (
          <span style={{ fontSize: 12, color: '#ffb84d', fontWeight: 600 }}>
            â¬¤ {nCambios} celda{nCambios !== 1 ? 's' : ''} sin guardar
          </span>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, border: '1px solid #34d399', borderRadius: 6, overflow: 'hidden' }}>
          <select
            value={excelPeriodo}
            onChange={e => setExcelPeriodo(e.target.value)}
            style={{ padding: '6px 6px', fontSize: 11, background: '#ECFDF5', color: '#34d399',
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
              background: '#ECFDF5', color: '#34d399', border: 'none', cursor: 'pointer' }}>
            â¬‡ Excel
          </button>
        </div>

        <button onClick={descartar} disabled={nCambios === 0}
          style={{ padding: '6px 14px', fontSize: 12, background: nCambios > 0 ? '#374151' : '#DDDDDD',
            color: nCambios > 0 ? '#e2e8f0' : '#4b5563', border: '1px solid #2a3348',
            borderRadius: 6, cursor: nCambios > 0 ? 'pointer' : 'not-allowed' }}>
          Descartar
        </button>
        <button onClick={guardar} disabled={guardando || nCambios === 0}
          style={{ padding: '6px 18px', fontSize: 13, fontWeight: 700,
            background: nCambios > 0 ? '#16a34a' : '#D1FAE5',
            color: nCambios > 0 ? '#fff' : '#3d6b4a',
            border: `2px solid ${nCambios > 0 ? '#16a34a' : '#CCCCCC'}`,
            borderRadius: 6, cursor: nCambios > 0 ? 'pointer' : 'not-allowed',
            boxShadow: nCambios > 0 ? '0 0 8px rgba(22,163,74,0.4)' : 'none',
            transition: 'all .2s' }}>
          {guardando
            ? <><span className="spinner" style={{ width: 12, height: 12 }} /> Guardando…</>
            : `ðŸ’¾ Guardar${nCambios > 0 ? ` (${nCambios})` : ''}`}
        </button>
      </div>

      {msg && (
        <div className={`alert alert-${msg.tipo === 'error' ? 'error' : 'success'}`}
          style={{ margin: '8px 20px', borderRadius: 8 }}>
          {msg.texto}
        </div>
      )}

      {/* ── Tabla pivot ─────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto' }}>
        {loading && filas.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, gap: 12, color: '#666666' }}>
            <span className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} /> Cargando...
          </div>
        ) : (
          <table style={{ borderCollapse: 'separate', borderSpacing: 0, tableLayout: 'fixed', width: 'max-content' }}>
            <thead>
              {/* ── Fila 1: Grupos ───────────────────────────────── */}
              <tr style={{ height: 28 }}>
                {/* Celdas fijas vacías en grupo */}
                {COLS_FIJAS.map((col, i) => (
                  <th key={col.key} style={{ ...thFijo(i), borderBottom: '1px solid #2a3348' }}>
                    {i === 0 ? `Forecast ${anio}` : ''}
                  </th>
                ))}
                {/* Grupos Q1-Q3 */}
                {q1vis && <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #0F766E', borderBottom:'1px solid #2a3348', letterSpacing:0.5 }}>Q1 — Ene · Feb · Mar</th>}
                {q2vis && <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #0F766E', borderBottom:'1px solid #2a3348', letterSpacing:0.5 }}>Q2 — Abr · May · Jun</th>}
                {q3vis && <th colSpan={3} style={{ background:'#E0F2FE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #0F766E', borderBottom:'1px solid #2a3348', letterSpacing:0.5 }}>Q3 — Jul · Ago · Sep</th>}
                {/* Q4: 6 columnas (2 por mes: actual + proyectado) */}
                {q4vis && <th colSpan={6} style={{ background:'#EDE9FE', color:'#a78bfa', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderRight:'2px solid #0F766E', borderBottom:'1px solid #2a3348', letterSpacing:0.5 }}>Q4 — Oct · Nov · Dic · &nbsp;⬡ Actual + Proyectado ANCLA-SI-MACRO</th>}
                {/* Total header */}
                <th style={{ background:'#DEDEDE', color:'#0D9488', fontSize:11, fontWeight:700, textAlign:'center', padding:'5px 8px', borderBottom:'1px solid #2a3348', minWidth:90 }}>TOTAL</th>
              </tr>

              {/* ── Fila 2a: Totales unidades ─────────────────────── */}
              <tr style={{ background: '#DEDEDE' }}>
                <th colSpan={999} style={{
                  position: 'sticky', left: 0, zIndex: 3,
                  background: '#DEDEDE', borderBottom: '1px solid #2a3348',
                  fontSize: 11, fontWeight: 700, padding: '5px 12px', textAlign: 'left',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ color: '#0D9488' }}>TOTAL &nbsp;</span>
                  <span style={{ color: '#666666', fontWeight: 400 }}>{clp(filasFiltradas.length)} SKUs · </span>
                  <span style={{ color: '#0D9488', fontFamily: 'var(--mono)' }}>{clp(totalUnits)} uds</span>
                </th>
              </tr>

              {/* ── Fila 2b: Venta neta ───────────────────────────── */}
              <tr style={{ background: '#E4E4E4' }}>
                <th colSpan={999} style={{
                  position: 'sticky', left: 0, zIndex: 3,
                  background: '#E4E4E4', borderBottom: '2px solid #3d7eff',
                  fontSize: 11, fontWeight: 700, padding: '5px 12px', textAlign: 'left',
                  whiteSpace: 'nowrap',
                }}>
                  <span style={{ color: '#666666', fontWeight: 400 }}>Venta Neta &nbsp;</span>
                  <span style={{ color: '#0D9488', fontFamily: 'var(--mono)', fontWeight: 700 }}>${mclp(totalVentaNeta)}</span>
                </th>
              </tr>

              {/* ── Fila 2c: Venta bruta por mes ─────────────────── */}
              <tr style={{ background: '#E8E8E8' }}>
                <th colSpan={COLS_FIJAS.length} style={{
                  position: 'sticky', left: 0, zIndex: 4,
                  background: '#E8E8E8', borderBottom: '1px solid #CCCCCC',
                  borderRight: '2px solid #3d7eff',
                  fontSize: 10, fontWeight: 600, padding: '4px 12px', textAlign: 'left',
                  whiteSpace: 'nowrap', color: '#64748b', fontStyle: 'italic',
                }}>
                  Venta Neta
                </th>
                {[0,1,2,3,4,5,6,7,8].filter(mi => mesVisible(mi)).map(mi => (
                  <th key={`vb_${mi}`} style={{
                    background: mi % 3 === 0 ? '#E0F2FE' : '#E8E8E8',
                    padding: '4px 4px', borderRight: '1px solid #DDDDDD',
                    borderBottom: '1px solid #CCCCCC',
                    fontSize: 10, color: '#475569', fontWeight: 600,
                    textAlign: 'center', whiteSpace: 'nowrap', minWidth: 60,
                  }}>
                    ${mclp(ventaNetaPorMes[mi])}
                  </th>
                ))}
                {q4vis && [9,10,11].map((mi, qi) => (
                  <React.Fragment key={`vb_q4_${mi}`}>
                    <th style={{
                      background: '#E0F2FE', padding: '4px 4px',
                      borderRight: '1px solid #DDDDDD', borderBottom: '1px solid #CCCCCC',
                      fontSize: 10, color: '#475569', fontWeight: 600,
                      textAlign: 'center', whiteSpace: 'nowrap', minWidth: 60,
                    }}>
                      ${mclp(ventaNetaPorMes[mi])}
                    </th>
                    <th style={{
                      background: '#EDE9FE', padding: '4px 4px',
                      borderRight: '1px solid #DDDDDD', borderBottom: '1px solid #CCCCCC',
                      fontSize: 10, color: '#7C3AED', fontWeight: 600,
                      textAlign: 'center', whiteSpace: 'nowrap', minWidth: 60,
                    }}>
                      ${mclp(ventaNetaProyQ4[qi])}
                    </th>
                  </React.Fragment>
                ))}
                <th style={{
                  background: '#E8E8E8', padding: '4px 4px',
                  borderBottom: '1px solid #CCCCCC',
                  fontSize: 10, color: '#0D9488', fontWeight: 700,
                  textAlign: 'center', whiteSpace: 'nowrap', minWidth: 90,
                }}>
                  ${mclp(totalVentaNeta)}
                </th>
              </tr>

              {/* ── Fila 3: Cabeceras mes ─────────────────────────── */}
              <tr>
                {COLS_FIJAS.map((col, i) => (
                  <th key={col.key} style={{ ...thFijo(i), zIndex: 5, top: 0 }}>
                    {col.label}
                  </th>
                ))}
                {/* Q1—Q3: una celda por mes */}
                {[0,1,2,3,4,5,6,7,8].filter(mi => mesVisible(mi)).map(mi => {
                  const hasFiltro = !!colFilters[mi]
                  const isSort = sortCol?.key === mi
                  return (
                    <th key={`hdr-${mi}`}
                      onClick={e => openFilter(e, mi)}
                      style={{ ...thMes(mi % 3 === 0), borderBottom: '2px solid #3d7eff', cursor: 'pointer', userSelect: 'none',
                        ...(isSort && { background: '#CCFBF1', color: '#14B8A6', borderBottom: '2px solid #60a5fa' }),
                        ...(hasFiltro && !isSort && { background: '#ECFDF5', color: '#34d399', borderBottom: '2px solid #34d399' }),
                      }}>
                      {MESES[mi]}
                      {isSort ? (sortCol.dir === 'desc' ? ' ↓' : ' ↑') : ''}
                      {hasFiltro && <span style={{ marginLeft: 2, fontSize: 9 }}>▼</span>}
                    </th>
                  )
                })}
                {/* Q4: dos cabeceras por mes */}
                {q4vis && [9,10,11].map((mi, qi) => {
                  const pk = `p${mi}`
                  const hasFiltro  = !!colFilters[mi]
                  const hasFiltroP = !!colFilters[pk]
                  const isSort  = sortCol?.key === mi
                  const isSortP = sortCol?.key === pk
                  return (
                  <React.Fragment key={`q4-hdr-${mi}`}>
                    <th onClick={e => openFilter(e, mi)}
                      style={{ ...thMes(true), borderBottom: '2px solid #3d7eff', color: '#c4b5fd', fontSize: 10,
                        cursor: 'pointer', userSelect: 'none',
                        ...(isSort && { background: '#EDE9FE', color: '#c4b5fd', borderBottom: '2px solid #a78bfa' }),
                        ...(hasFiltro && !isSort && { background: '#ECFDF5', color: '#34d399', borderBottom: '2px solid #34d399' }),
                      }}>
                      {MESES[mi]}
                      {isSort ? (sortCol.dir === 'desc' ? ' ↓' : ' ↑') : ''}
                      {hasFiltro && <span style={{ marginLeft: 2, fontSize: 9 }}>▼</span>}
                    </th>
                    <th onClick={e => openFilter(e, pk)}
                      style={{
                        background: isSortP ? '#EDE9FE' : hasFiltroP ? '#ECFDF5' : '#F0F0F0',
                        padding: '6px 4px', cursor: 'pointer', userSelect: 'none',
                        borderRight: qi === 2 ? '2px solid #0F766E' : '1px solid #2a3348',
                        borderBottom: isSortP ? '2px solid #a78bfa' : hasFiltroP ? '2px solid #34d399' : '2px solid #3d7eff',
                        fontSize: 9, fontWeight: 700, textAlign: 'center', minWidth: 60, whiteSpace: 'nowrap',
                        color: isSortP ? '#c4b5fd' : hasFiltroP ? '#34d399' : '#7c5cde',
                      }}>
                      ⬡ Proy.{isSortP ? (sortCol.dir === 'desc' ? ' ↓' : ' ↑') : ''}
                      {hasFiltroP && !isSortP && <span style={{ marginLeft: 2 }}>▼</span>}
                    </th>
                  </React.Fragment>
                  )
                })}
                <th style={{ ...thMes(true), borderBottom: '2px solid #3d7eff', color: '#0D9488' }}>TOTAL</th>
              </tr>

              {/* ── Fila 4: Filtros tipo Excel ────────────────────── */}
              <tr style={{ background: '#EBEBEB' }}>
                <th style={{ ...thFijo(0), background: '#EBEBEB', padding: '4px 4px' }}>
                  <MultiSelect dark options={opMarcas} value={filtros.marca}
                    onChange={v => setFiltro('marca', v)} placeholder="▼ Marca" />
                </th>
                <th style={{ ...thFijo(1), background: '#EBEBEB', padding: '4px 4px' }}>
                  <input value={filtros.sku} onChange={e => setFiltro('sku', e.target.value)}
                    placeholder='Buscar…' style={{ width: '100%', fontSize: 10, background: '#EBEBEB',
                      color: filtros.sku ? '#0D9488' : '#666666', border: `1px solid ${filtros.sku ? '#0D9488' : '#CCCCCC'}`,
                      borderRadius: 3, padding: '2px 4px' }} />
                </th>
                <th style={{ ...thFijo(2), background: '#EBEBEB', padding: '4px 4px' }}>
                  <input value={filtros.descripcion} onChange={e => setFiltro('descripcion', e.target.value)}
                    placeholder='Buscar…' style={{ width: '100%', fontSize: 10, background: '#EBEBEB',
                      color: filtros.descripcion ? '#0D9488' : '#666666', border: `1px solid ${filtros.descripcion ? '#0D9488' : '#CCCCCC'}`,
                      borderRadius: 3, padding: '2px 4px' }} />
                </th>
                <th style={{ ...thFijo(3), background: '#EBEBEB', padding: '4px 4px' }}>
                  <MultiSelect dark options={opSubcategorias} value={filtros.subcategoria}
                    onChange={v => setFiltro('subcategoria', v)} placeholder="▼ Subcategoría" />
                </th>
                <th style={{ ...thFijo(4), background: '#EBEBEB', padding: '4px 4px' }}>
                  <MultiSelect dark options={opTipoProductos} value={filtros.tipo_producto}
                    onChange={v => setFiltro('tipo_producto', v)} placeholder="▼ Tipo de Producto" />
                </th>
                <th style={{ ...thFijo(5), background: '#EBEBEB', padding: '4px 4px', borderBottom: '2px solid #3d7eff' }}>
                  <MultiSelect dark options={temporadas.map(t => t.nombre)} value={filtroTemp}
                    onChange={setFiltroTemp} placeholder="▼ Temporada" />
                </th>
                {/* Q1—Q3 filtros vacíos */}
                {[0,1,2,3,4,5,6,7,8].filter(mi => mesVisible(mi)).map(mi => (
                  <th key={`flt-${mi}`} style={{ background: '#EBEBEB', borderRight: '1px solid #DDDDDD', borderBottom: '2px solid #3d7eff', minWidth: 60 }} />
                ))}
                {/* Q4: dos vacíos por mes */}
                {q4vis && [9,10,11].map((mi, qi) => (
                  <React.Fragment key={`q4-flt-${mi}`}>
                    <th style={{ background: '#EBEBEB', borderRight: '1px solid #DDDDDD', borderBottom: '2px solid #3d7eff', minWidth: 60 }} />
                    <th style={{ background: '#E8E8E8', borderRight: qi === 2 ? '2px solid #0F766E' : '1px solid #DDDDDD', borderBottom: '2px solid #3d7eff', minWidth: 60 }} />
                  </React.Fragment>
                ))}
                <th style={{ background: '#EBEBEB', borderBottom: '2px solid #3d7eff', minWidth: 90 }} />
              </tr>
            </thead>

            <tbody>
              {filasSorted.map((fila, ri) => {
                const bgBase  = ri % 2 === 0 ? '#F5F5F5' : '#F0F0F0'
                const totalFc = MESES.reduce((s, _, mi) => s + getVal(fila.sku, mi), 0)
                const totalPq = MESES.reduce((s, _, mi) => s + getVal(fila.sku, mi) * fila.precio_lp, 0)
                const esInactivo = fila.activo === false

                return (
                  <React.Fragment key={fila.sku}>
                  <tr style={{ height: 34, opacity: esInactivo ? 0.45 : 1 }}>
                    {/* ── Columnas fijas ── */}
                    <td style={{ ...tdFijo(0, bgBase), color: '#0D9488', fontWeight: 600, fontSize: 11 }}>
                      {fila.marca || '—'}
                    </td>
                    <td style={{ ...tdFijo(1, bgBase), color: '#0D9488', fontFamily: 'var(--mono)', fontSize: 11 }}>
                      <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                        {fila.sku}
                        <span
                          title="Análisis de stock"
                          onClick={e => { e.stopPropagation(); setSkuStockModal(fila.sku) }}
                          style={{ cursor:'pointer', fontSize:11, opacity:0.5, lineHeight:1, userSelect:'none' }}
                          onMouseEnter={e => e.currentTarget.style.opacity='1'}
                          onMouseLeave={e => e.currentTarget.style.opacity='0.5'}
                        >ðŸ“¦</span>
                      </span>
                    </td>
                    <td style={{ ...tdFijo(2, bgBase), color: fila.por_discontinuar ? '#fbbf24' : '#111111' }}
                      title={
                        (fila.descripcion || '') +
                        (fila.por_discontinuar ? ` · Por discontinuar${fila.mes_agota_stock ? ` (stock agota mes ${fila.mes_agota_stock})` : ''}` : '') +
                        (fila.compras_necesarias ? ` · Comprar ${fila.compras_necesarias} uds` : '')
                      }>
                      {fila.por_discontinuar && (
                        <span style={{ fontSize: 9, background: '#78350f', color: '#fbbf24',
                          borderRadius: 3, padding: '1px 3px', marginRight: 3, fontWeight: 700,
                          verticalAlign: 'middle' }}>
                          DISC{fila.mes_agota_stock ? ` M${fila.mes_agota_stock}` : ''}
                        </span>
                      )}
                      {fila.compras_necesarias > 0 && (
                        <span style={{ fontSize: 9, background: '#E0F2FE', color: '#14B8A6',
                          borderRadius: 3, padding: '1px 3px', marginRight: 3, fontWeight: 700,
                          verticalAlign: 'middle' }}
                          title={`Compras necesarias: ${fila.compras_necesarias} uds`}>
                          ▲{clp(fila.compras_necesarias)}
                        </span>
                      )}
                      {fila.descripcion || '—'}
                    </td>
                    <td style={{ ...tdFijo(3, bgBase), color: '#666666', fontSize: 11 }} title={fila.categoria || ''}>
                      {fila.subcategoria || fila.categoria || '—'}
                    </td>
                    <td style={{ ...tdFijo(4, bgBase), color: fila.tipo_producto ? '#666666' : '#ef4444', fontSize: 11 }}
                        title={fila.tipo_producto ? fila.tipo_producto : 'Sin clasificar'}>
                      {fila.tipo_producto || <em style={{opacity:0.5}}>—</em>}
                    </td>
                    <td style={{ ...tdFijo(5, bgBase), color: '#666666', fontSize: 11 }}>
                      {fila.temporada || '—'}
                    </td>

                    {/* ── Celdas Q1—Q3 (editables) ── */}
                    {[0,1,2,3,4,5,6,7,8].filter(mi => mesVisible(mi)).map(mi => {
                      const key      = `${fila.sku}|${mi}`
                      const estaEdit = editando === key
                      const val      = getVal(fila.sku, mi)
                      const cambiado = key in cambios
                      const pxq      = val * fila.precio_lp
                      return (
                        <td key={key} onClick={() => !estaEdit && startEdit(fila.sku, mi)}
                          style={{
                            minWidth: 60, maxWidth: 60, padding: 0,
                            borderRight: '1px solid #DDDDDD', borderBottom: '1px solid #DDDDDD',
                            background: cambiado ? 'rgba(255,184,77,0.18)' : bgBase,
                            cursor: 'pointer', verticalAlign: 'middle',
                          }}
                          title={pxq > 0 ? `PxQ: $${clp(pxq)}` : ''}>
                          {estaEdit ? (
                            <input ref={inputRef} type="number" min={0} value={valEdit}
                              onChange={e => setValEdit(e.target.value)}
                              onBlur={() => commitEdit(fila.sku, mi)}
                              onKeyDown={e => handleKeyDown(e, fila.sku, mi)}
                              style={{ width: '100%', height: '100%', background: '#FFFFFF',
                                border: '2px solid #3d7eff', color: '#fff',
                                fontFamily: 'var(--mono)', fontSize: 12,
                                textAlign: 'center', padding: '4px 2px', boxSizing: 'border-box' }} />
                          ) : (
                            <div style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12,
                              padding: '4px 4px',
                              color: val === 0 ? '#BBBBBB' : cambiado ? '#ffb84d' : '#111111',
                              fontWeight: cambiado ? 700 : 400 }}>
                              {val === 0 ? '-' : clp(val)}
                              {val > 0 && <div style={{ fontSize: 9, color: '#888888', marginTop: 1 }}>${mclp(pxq)}</div>}
                            </div>
                          )}
                        </td>
                      )
                    })}

                    {/* ── Celdas Q4: actual (editable) + proyectado (solo lectura) ── */}
                    {q4vis && [9,10,11].map((mi, qi) => {
                      const key      = `${fila.sku}|${mi}`
                      const estaEdit = editando === key
                      const val      = getVal(fila.sku, mi)
                      const cambiado = key in cambios
                      const pxq      = val * fila.precio_lp
                      const proy     = getQ4(fila.sku, mi)
                      const diff     = proy != null && val > 0 ? Math.round(((proy - val) / val) * 100) : null
                      return (
                        <React.Fragment key={`q4-cell-${fila.sku}-${mi}`}>
                          {/* Celda actual (editable) */}
                          <td onClick={() => !estaEdit && startEdit(fila.sku, mi)}
                            style={{
                              minWidth: 60, maxWidth: 60, padding: 0,
                              borderRight: '1px solid #DDDDDD', borderBottom: '1px solid #DDDDDD',
                              background: cambiado ? 'rgba(255,184,77,0.18)' : bgBase,
                              cursor: 'pointer', verticalAlign: 'middle',
                            }}
                            title={pxq > 0 ? `PxQ: $${clp(pxq)}` : ''}>
                            {estaEdit ? (
                              <input ref={inputRef} type="number" min={0} value={valEdit}
                                onChange={e => setValEdit(e.target.value)}
                                onBlur={() => commitEdit(fila.sku, mi)}
                                onKeyDown={e => handleKeyDown(e, fila.sku, mi)}
                                style={{ width: '100%', height: '100%', background: '#FFFFFF',
                                  border: '2px solid #3d7eff', color: '#fff',
                                  fontFamily: 'var(--mono)', fontSize: 12,
                                  textAlign: 'center', padding: '4px 2px', boxSizing: 'border-box' }} />
                            ) : (
                              <div style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12,
                                padding: '4px 4px',
                                color: val === 0 ? '#BBBBBB' : cambiado ? '#ffb84d' : '#111111',
                                fontWeight: cambiado ? 700 : 400 }}>
                                {val === 0 ? '-' : clp(val)}
                                {val > 0 && <div style={{ fontSize: 9, color: '#888888', marginTop: 1 }}>${mclp(pxq)}</div>}
                              </div>
                            )}
                          </td>
                          {/* Celda proyectado (editable) */}
                          {(() => {
                            const pkeyStr = `${fila.sku}|${mi}`
                            const editProy = editando === `proy:${pkeyStr}`
                            const editarProy = () => {
                              setEditando(`proy:${pkeyStr}`)
                              setValEdit(String(proy ?? 0))
                            }
                            const commitProy = () => {
                              const nuevo = Math.max(0, parseInt(valEdit) || 0)
                              const orig = proyeccionQ4[fila.sku]?.[mi + 1] ?? null
                              setCambiosQ4Proy(p => {
                                const next = { ...p }
                                if (orig !== null && nuevo === orig) delete next[pkeyStr]
                                else next[pkeyStr] = nuevo
                                return next
                              })
                              setEditando(null)
                            }
                            const cambioProy = pkeyStr in cambiosQ4Proy
                            return (
                              <td key={`${key}-proy`}
                                onClick={() => !editProy && editarProy()}
                                style={{
                                  minWidth: 60, maxWidth: 60, padding: 0,
                                  borderRight: qi === 2 ? '2px solid #0F766E' : '1px solid #2a3348',
                                  borderBottom: '1px solid #DDDDDD',
                                  background: cambioProy ? 'rgba(167,139,250,0.15)' : '#F5F3FF',
                                  cursor: 'pointer', verticalAlign: 'middle',
                                }}
                                title="Proyección ANCLA-SI-MACRO — editable">
                                {editProy ? (
                                  <input ref={inputRef} type="number" min={0} value={valEdit}
                                    onChange={e => setValEdit(e.target.value)}
                                    onBlur={commitProy}
                                    onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); commitProy() } if (e.key === 'Escape') setEditando(null) }}
                                    style={{ width: '100%', height: '100%', background: '#2d1a5e',
                                      border: '2px solid #7c3aed', color: '#e9d5ff',
                                      fontFamily: 'var(--mono)', fontSize: 12,
                                      textAlign: 'center', padding: '4px 2px', boxSizing: 'border-box' }} />
                                ) : (
                                  <div style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12,
                                    padding: '4px 4px',
                                    color: proy == null ? '#CCCCCC' : cambioProy ? '#e9d5ff' : '#a78bfa',
                                    fontWeight: cambioProy ? 700 : 400 }}>
                                    {proy == null ? '—' : clp(proy)}
                                    {diff != null && (
                                      <div style={{ fontSize: 9, marginTop: 1,
                                        color: diff > 0 ? '#34d399' : diff < 0 ? '#f87171' : '#6b7280' }}>
                                        {diff > 0 ? '+' : ''}{diff}%
                                      </div>
                                    )}
                                  </div>
                                )}
                              </td>
                            )
                          })()}
                        </React.Fragment>
                      )
                    })}

                    {/* ── Columna TOTAL ── */}
                    <td style={{
                      minWidth: 90, textAlign: 'center',
                      borderBottom: vs2025 ? 'none' : '1px solid #DDDDDD',
                      background: bgBase,
                      padding: '4px 8px',
                    }}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: totalFc > 0 ? '#0D9488' : '#BBBBBB', fontWeight: 600 }}>
                        {totalFc === 0 ? '—' : clp(totalFc)}
                      </div>
                      {totalPq > 0 && (
                        <div style={{ fontSize: 9, color: '#888888', marginTop: 1 }}>
                          ${mclp(totalPq)}
                        </div>
                      )}
                    </td>
                  </tr>

                  {/* ── Sub-fila vs 2025 ── */}
                  {vs2025 && (() => {
                    const v25 = fila.ventas_2025 || Array(12).fill(0)
                    const totalV25 = v25.reduce((s, x) => s + x, 0)
                    const tdV25 = (mi, isQ4) => {
                      const real25 = v25[mi]
                      const fc26   = getVal(fila.sku, mi)
                      const proy26 = isQ4 ? (getQ4(fila.sku, mi) ?? 0) : null
                      const ref    = isQ4 ? proy26 : fc26
                      const pct    = ref != null && real25 > 0 ? Math.round(((ref - real25) / real25) * 100) : null
                      return (
                        <td key={`v25-${mi}${isQ4?'p':''}`} style={{
                          minWidth: 60, maxWidth: 60, padding: '2px 4px',
                          borderRight: '1px solid #DDDDDD', borderBottom: '1px solid #DDDDDD',
                          background: '#E8E8E8', verticalAlign: 'middle', textAlign: 'center',
                        }}>
                          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: real25 === 0 ? '#BBBBBB' : '#f59e0b' }}>
                            {real25 === 0 ? '—' : clp(real25)}
                          </div>
                          {pct !== null && (
                            <div style={{ fontSize: 9, color: pct >= 0 ? '#34d399' : '#f87171', marginTop: 0 }}>
                              {pct >= 0 ? '+' : ''}{pct}%
                            </div>
                          )}
                        </td>
                      )
                    }
                    const colsFijas = COLS_FIJAS.length
                    return (
                      <tr key={`${fila.sku}-v25`} style={{ height: 26 }}>
                        <td colSpan={colsFijas} style={{
                          padding: '2px 8px', background: '#E8E8E8',
                          borderBottom: '1px solid #DDDDDD',
                          color: '#f59e0b', fontSize: 9, fontWeight: 700,
                          position: 'sticky', left: 0, zIndex: 2,
                        }}>â–¶ 2025 real</td>
                        {[0,1,2,3,4,5,6,7,8].filter(mi => mesVisible(mi)).map(mi => tdV25(mi, false))}
                        {q4vis && [9,10,11].map(mi => (
                          <React.Fragment key={`v25-q4-${mi}`}>
                            {tdV25(mi, false)}
                            {tdV25(mi, true)}
                          </React.Fragment>
                        ))}
                        <td style={{
                          minWidth: 90, padding: '2px 8px', background: '#E8E8E8',
                          borderBottom: '1px solid #DDDDDD', textAlign: 'center',
                          fontFamily: 'var(--mono)', fontSize: 10, color: totalV25 === 0 ? '#BBBBBB' : '#f59e0b',
                        }}>{totalV25 === 0 ? '—' : clp(totalV25)}</td>
                      </tr>
                    )
                  })()}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
    {FilterPopover}
    {skuStockModal && (
      <StockAnalisisModal sku={skuStockModal} onClose={() => setSkuStockModal(null)} />
    )}
    </>
  )
}

