import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import * as XLSX from "xlsx"
import { getForecastTabla, aplicarProyeccion, getTemporadas } from "../../../services/api"
import { MESES, ANIO, PERIODOS, MESES_Q, clp, mclp } from "../utils/forecastUtils"

export function useForecastTabla(anio = ANIO) {
  // ── State ───────────────────────────────────────────────────────────────
  const [filas,         setFilas]         = useState([])
  const [loading,       setLoading]       = useState(false)
  const [guardando,     setGuardando]     = useState(false)
  const [msg,           setMsg]           = useState(null)
  const [temporadas,    setTemporadas]    = useState([])
  const [filtroTemp,      setFiltroTemp]      = useState([])
  const [filtroCategoria, setFiltroCategoria] = useState([])
  const [filtros,         setFiltros]         = useState({ marca: [], sku: '', descripcion: '', subcategoria: [], tipo_producto: [] })
  const [proyeccionQ4,     setProyeccionQ4]     = useState({}) // {sku: {10: qty, 11: qty, 12: qty}} (1-based)
  const [cambiosQ4Proy,    setCambiosQ4Proy]    = useState({}) // {"sku|mes": qty} ediciones proyectado
  const [guardandoQ4Proy,  setGuardandoQ4Proy]  = useState(false)
  const [vs2025,           setVs2025]           = useState(false)
  const [filtroQ,          setFiltroQ]          = useState('todo') // 'todo'|'q1'|'q2'|'q3'|'q4'
  const [sortCol,          setSortCol]          = useState(null)   // null | { key, dir: 'desc'|'asc' }
  const [sortBy,           setSortBy]           = useState('descripcion')
  const [sortDir,          setSortDir]          = useState('asc')
  const [colFilters,       setColFilters]       = useState({})     // { [key]: { tipo:'gt'|'lt'|'nozero', valor:number } }
  const [filterPopover,    setFilterPopover]    = useState(null)   // { key, x, y } | null
  const [filterInput,      setFilterInput]      = useState({ gt: '', lt: '' })
  const [skuStockModal,    setSkuStockModal]    = useState(null)
  const [excelPeriodo,     setExcelPeriodo]     = useState('m9')

  // cambios pendientes: { "sku|mes": número }
  const [cambios, setCambios] = useState({})
  // celda en edición: "sku|mes" | null
  const [editando, setEditando] = useState(null)
  const [valEdit,  setValEdit]  = useState('')
  const inputRef = useRef()

  // ── Effects ─────────────────────────────────────────────────────────────
  useEffect(() => {
    getTemporadas().then(setTemporadas).catch(() => {})
    cargar()
    fetch('/api/forecast/proyeccion-q4')
      .then(r => r.ok ? r.json() : {})
      .then(setProyeccionQ4)
      .catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (editando && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editando])

  // ── Cargar datos ────────────────────────────────────────────────────────
  async function cargar() {
    setLoading(true); setMsg(null); setCambios({})
    try {
      const params = { anio }
      const data = await getForecastTabla(params)
      setFilas(data)
    } catch (e) {
      setMsg({ tipo: 'error', texto: e.message })
    } finally {
      setLoading(false)
    }
  }

  // ── Valor actual de una celda (cambio pendiente o valor original) ────────
  function getVal(sku, mesIdx) {
    const key = `${sku}|${mesIdx}`
    return key in cambios ? cambios[key] : (filas.find(f => f.sku === sku)?.forecast[mesIdx] ?? 0)
  }

  // ── Edición de celdas ───────────────────────────────────────────────────
  function startEdit(sku, mesIdx) {
    const key = `${sku}|${mesIdx}`
    setEditando(key)
    setValEdit(String(getVal(sku, mesIdx)))
  }

  function commitEdit(sku, mesIdx) {
    const key   = `${sku}|${mesIdx}`
    const fila  = filas.find(f => f.sku === sku)
    const orig  = fila?.forecast[mesIdx] ?? 0
    const nuevo = Math.max(0, parseInt(valEdit) || 0)
    setCambios(p => {
      const next = { ...p }
      if (nuevo === orig) delete next[key]
      else next[key] = nuevo
      return next
    })
    setEditando(null)
  }

  function handleKeyDown(e, sku, mesIdx) {
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      commitEdit(sku, mesIdx)
      const nextMes = mesIdx + (e.shiftKey ? -1 : 1)
      if (nextMes >= 0 && nextMes < 12) startEdit(sku, nextMes)
    }
    if (e.key === 'Escape') { setEditando(null) }
  }

  // ── Guardar forecast ────────────────────────────────────────────────────
  async function guardar() {
    const items = Object.entries(cambios).map(([key, cantidad]) => {
      const [sku, mesIdx] = key.split('|')
      return { sku, anio, mes: parseInt(mesIdx) + 1, cantidad }
    })
    if (!items.length) return
    setGuardando(true); setMsg(null)
    try {
      const res = await aplicarProyeccion(items)
      const upd = res.filter(r => r.accion !== 'sin_cambio').length
      setMsg({ tipo: 'success', texto: `✓ ${upd} celda${upd !== 1 ? 's' : ''} guardada${upd !== 1 ? 's' : ''}` })
      setCambios({})
      cargar()
    } catch (e) {
      setMsg({ tipo: 'error', texto: e.message })
    } finally {
      setGuardando(false)
    }
  }

  function descartar() { setCambios({}); setEditando(null) }

  // ── Proyección Q4 ───────────────────────────────────────────────────────
  const getQ4 = useCallback((sku, mi) => {
    const fila = filas.find(f => f.sku === sku)
    if (fila) {
      const temp = (fila.temporada || '').toLowerCase()
      if (temp.includes('invierno') && [9, 10, 11].includes(mi)) return 0
    }
    const key = `${sku}|${mi}`
    return key in cambiosQ4Proy ? cambiosQ4Proy[key] : (proyeccionQ4[sku]?.[mi + 1] ?? null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filas, cambiosQ4Proy, proyeccionQ4])

  async function guardarQ4Proy() {
    const items = Object.entries(cambiosQ4Proy).map(([key, cantidad]) => {
      const [sku, mi] = key.split('|')
      return { sku, mes: parseInt(mi) + 1, cantidad }
    })
    if (!items.length) return
    setGuardandoQ4Proy(true)
    try {
      await fetch('/api/forecast/proyeccion-q4/upsert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(items),
      })
      setProyeccionQ4(prev => {
        const next = { ...prev }
        items.forEach(({ sku, mes, cantidad }) => {
          next[sku] = { ...(next[sku] || {}), [mes]: cantidad }
        })
        return next
      })
      setCambiosQ4Proy({})
    } catch (e) {
      setMsg({ tipo: 'error', texto: 'Error al guardar proyección Q4: ' + e.message })
    } finally {
      setGuardandoQ4Proy(false)
    }
  }

  // ── Filtros de columna (valor de celda) ─────────────────────────────────
  // clave de columna: número 0-11 = real, string 'p9'/'p10'/'p11' = proyectado Q4
  const getValKey = useCallback((fila, key) => {
    if (typeof key === 'string' && key.startsWith('p')) {
      const mi = parseInt(key.slice(1))
      return getQ4(fila.sku, mi) ?? 0
    }
    return getVal(fila.sku, key)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getQ4, cambios, filas])

  const openFilter = (e, key) => {
    e.stopPropagation()
    if (filterPopover?.key === key) { setFilterPopover(null); return }
    const rect = e.currentTarget.getBoundingClientRect()
    const f = colFilters[key] || {}
    setFilterInput({ gt: f.tipo === 'gt' ? String(f.valor) : '', lt: f.tipo === 'lt' ? String(f.valor) : '' })
    setFilterPopover({ key, x: Math.min(rect.left, window.innerWidth - 220), y: rect.bottom + 4 })
  }

  const applyFilter = (key, tipo, valor) => {
    setColFilters(prev => {
      const next = { ...prev }
      if (!tipo) { delete next[key]; return next }
      next[key] = { tipo, valor: Number(valor) || 0 }
      return next
    })
    setFilterPopover(null)
  }

  const toggleSort = (key, dir) => {
    setSortCol(prev => prev?.key === key && prev.dir === dir ? null : { key, dir })
    setFilterPopover(null)
  }

  // ── Opciones únicas para dropdowns ──────────────────────────────────────
  // filasSinCateg: para opciones dinámicas del dropdown Cat. Principal
  const filasSinCateg = useMemo(() => filas.filter(f => {
    if (filtroTemp.length          && !filtroTemp.includes(f.temporada))                    return false
    if (filtros.marca.length       && !filtros.marca.includes(f.marca))                     return false
    if (filtros.subcategoria.length && !filtros.subcategoria.includes(f.subcategoria))      return false
    if (filtros.tipo_producto.length && !filtros.tipo_producto.includes(f.tipo_producto))   return false
    if (filtros.sku         && !f.sku.toLowerCase().includes(filtros.sku.toLowerCase()))    return false
    if (filtros.descripcion && !f.descripcion?.toLowerCase().includes(filtros.descripcion.toLowerCase())) return false
    return true
  }), [filas, filtros, filtroTemp])

  const opMarcas        = useMemo(() => [...new Set(filas.map(f => f.marca).filter(Boolean))].sort(), [filas])
  const opCategorias    = useMemo(() => [...new Set(filasSinCateg.map(f => f.categoria).filter(Boolean))].sort(), [filasSinCateg])
  const opSubcategorias = useMemo(() => [...new Set(filas.map(f => f.subcategoria).filter(Boolean))].sort(), [filas])
  const opTipoProductos = useMemo(() => [...new Set(filas.map(f => f.tipo_producto).filter(Boolean))].sort(), [filas])

  // ── Filas filtradas (client-side) ────────────────────────────────────────
  const filasFiltradas = useMemo(() => {
    return filas.filter(f => {
      if (filtroCategoria.length  && !filtroCategoria.includes(f.categoria))   return false
      if (filtroTemp.length       && !filtroTemp.includes(f.temporada))         return false
      if (filtros.marca.length    && !filtros.marca.includes(f.marca))          return false
      if (filtros.subcategoria.length && !filtros.subcategoria.includes(f.subcategoria)) return false
      if (filtros.tipo_producto.length && !filtros.tipo_producto.includes(f.tipo_producto)) return false
      if (filtros.sku         && !f.sku.toLowerCase().includes(filtros.sku.toLowerCase())) return false
      if (filtros.descripcion && !f.descripcion?.toLowerCase().includes(filtros.descripcion.toLowerCase())) return false
      return true
    })
  }, [filas, filtros, filtroCategoria, filtroTemp])

  const hayFiltros = filtros.marca.length > 0 || filtros.sku !== '' || filtros.descripcion !== '' ||
    filtros.subcategoria.length > 0 || filtros.tipo_producto.length > 0 ||
    filtroCategoria.length > 0 || filtroTemp.length > 0

  // ── Filtro y orden por mes ───────────────────────────────────────────────
  const filasConFiltroMes = useMemo(() => {
    let rows = filasFiltradas
    Object.entries(colFilters).forEach(([key, f]) => {
      const k = isNaN(Number(key)) ? key : Number(key)
      rows = rows.filter(fila => {
        const val = getValKey(fila, k)
        if (f.tipo === 'nozero') return val > 0
        if (f.tipo === 'gt')    return val > f.valor
        if (f.tipo === 'lt')    return val < f.valor
        return true
      })
    })
    return rows
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filasFiltradas, colFilters])

  const filasSorted = useMemo(() => {
    if (sortCol) {
      const { key, dir } = sortCol
      const k = isNaN(Number(key)) ? key : Number(key)
      return [...filasConFiltroMes].sort((a, b) => {
        const va = getValKey(a, k)
        const vb = getValKey(b, k)
        return dir === 'desc' ? vb - va : va - vb
      })
    }
    const dir = sortDir === 'asc' ? 1 : -1
    return [...filasConFiltroMes].sort((a, b) => {
      let va, vb
      if (sortBy === 'marca')      { va = a.marca || ''; vb = b.marca || '' }
      else if (sortBy === 'sku')   { va = a.sku || '';   vb = b.sku || '' }
      else                         { va = a.descripcion || ''; vb = b.descripcion || '' }
      return va.localeCompare(vb) * dir
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filasConFiltroMes, sortCol, sortBy, sortDir])

  // ── Totales ──────────────────────────────────────────────────────────────
  const totalesPorMes = MESES.map((_, mi) =>
    filasFiltradas.reduce((s, f) => s + getVal(f.sku, mi), 0)
  )
  const totalesQ4Proy = [9, 10, 11].map(mi =>
    filasFiltradas.reduce((s, f) => s + (getQ4(f.sku, mi) ?? 0), 0)
  )
  const pxqMes = (mi) => filasFiltradas.reduce((s, f) => s + getVal(f.sku, mi) * f.precio_lp, 0)
  const ventaNetaPorMes = MESES.map((_, mi) => pxqMes(mi) / 1.19)
  const totalPxQ       = MESES.reduce((s, _, mi) => s + pxqMes(mi), 0)
  const totalVentaNeta = totalPxQ / 1.19

  const ventaNetaProyQ4 = [9, 10, 11].map(mi =>
    filasFiltradas.reduce((s, f) => s + (getQ4(f.sku, mi) ?? 0) * f.precio_lp, 0) / 1.19
  )
  const totalNetoPrQ4 = ventaNetaProyQ4.reduce((s, v) => s + v, 0)

  // ── Filtro de quarter / mes individual ──────────────────────────────────
  const mesVisible = (mi) => !MESES_Q[filtroQ] || MESES_Q[filtroQ].includes(mi)
  const q1vis = filtroQ === 'todo' || filtroQ === 'q1'
  const q2vis = filtroQ === 'todo' || filtroQ === 'q2'
  const q3vis = filtroQ === 'todo' || filtroQ === 'q3'
  const q4vis = filtroQ === 'todo' || filtroQ === 'q4' || filtroQ === 'm9' || filtroQ === 'm10' || filtroQ === 'm11'

  // ── Neto del quarter/mes seleccionado ────────────────────────────────────
  const netoQSeleccionado = (() => {
    const indices = MESES_Q[filtroQ]
    if (!indices) return null
    const fcNeto   = indices.reduce((s, mi) => s + ventaNetaPorMes[mi], 0)
    const proyNeto = indices.filter(mi => [9,10,11].includes(mi))
                            .reduce((s, mi) => s + ventaNetaProyQ4[[9,10,11].indexOf(mi)], 0)
    return { fcNeto, proyNeto, label: filtroQ.toUpperCase() }
  })()

  // ── Contadores y helpers de UI ───────────────────────────────────────────
  const nCambiosQ4Proy = Object.keys(cambiosQ4Proy).length
  const totalUnits = totalesPorMes.reduce((s, v) => s + v, 0)
  const nCambios   = Object.keys(cambios).length
  const setFiltro  = (k, v) => setFiltros(p => ({ ...p, [k]: v }))

  function limpiarFiltros() {
    setFiltros({ marca:[], sku:'', descripcion:'', subcategoria:[], tipo_producto:[] })
    setFiltroCategoria([])
    setFiltroTemp([])
  }

  // ── Exportar Excel ───────────────────────────────────────────────────────
  function exportarPeriodo() {
    const p = excelPeriodo
    const meses_idx = p.startsWith('m') ? [parseInt(p.slice(1))]
      : p === 'q1' ? [0,1,2] : p === 'q2' ? [3,4,5]
      : p === 'q3' ? [6,7,8] : p === 'q4' ? [9,10,11]
      : [0,1,2,3,4,5,6,7,8,9,10,11]
    const label = PERIODOS.find(x => x.val === p)?.label || p

    const rows = filasFiltradas.map(fila => {
      const row = {
        'SKU':          fila.sku,
        'Descripción':  fila.descripcion || '',
        'Marca':        fila.marca || '',
        'Subcategoría': fila.subcategoria || '',
        'Tipo':         fila.tipo_producto || '',
        'Temporada':    fila.temporada || '',
        'Precio LP':    fila.precio_lp || 0,
        'Precio Neto':  Math.round(fila.precio_neto || (fila.precio_lp || 0) / 1.19),
      }
      meses_idx.forEach(mi => {
        const fc   = getVal(fila.sku, mi)
        const proy = getQ4(fila.sku, mi) ?? 0
        row[`Fc ${MESES[mi]}`]   = fc
        row[`Proy ${MESES[mi]}`] = proy
        row[`PxQ ${MESES[mi]}`]  = Math.round(fc * (fila.precio_lp || 0))
      })
      return row
    })

    const ws = XLSX.utils.json_to_sheet(rows)
    ws['!cols'] = [
      { wch: 12 }, { wch: 40 }, { wch: 14 }, { wch: 18 }, { wch: 22 }, { wch: 12 },
      { wch: 12 }, { wch: 12 },
      ...meses_idx.flatMap(() => [{ wch: 12 }, { wch: 12 }, { wch: 14 }]),
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, label)
    XLSX.writeFile(wb, `forecast_${label.toLowerCase().replace(/[^a-z0-9]/g,'_')}_2026.xlsx`)
  }

  // ── Return ───────────────────────────────────────────────────────────────
  return {
    // State de datos
    filas, loading, guardando, msg, temporadas,

    // Filtros globales
    filtroTemp, setFiltroTemp,
    filtroCategoria, setFiltroCategoria,
    filtros, setFiltro, limpiarFiltros,
    hayFiltros,

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
  }
}
