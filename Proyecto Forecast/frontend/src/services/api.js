// src/services/api.js
// En local (npm run dev) usa el proxy de Vite a /api.
// En Cloudflare Pages, configura VITE_API_URL con la URL del backend en Render
// (ej: https://forecast-dcic-backend.onrender.com/api).
const BASE = import.meta.env.VITE_API_URL || "/api"

function getToken() {
  return localStorage.getItem('dcic_token') || ''
}

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${getToken()}`,
      ...options.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Error en el servidor")
  }
  return res.status === 204 ? null : res.json()
}

// Temporadas
export const getTemporadas = () => req("/temporadas/")

// Marcas
export const getMarcas = () => req("/marcas/")

// Categorías
export const getCategorias = () => req("/categorias/")

// Productos
export const getProductos       = ()              => req("/productos/?limit=2000")
export const crearProducto      = (data)          => req("/productos/", { method: "POST", body: JSON.stringify(data) })
export const actualizarProducto = (sku, data)     => req(`/productos/${sku}`, { method: "PUT", body: JSON.stringify(data) })
export const eliminarProducto   = (sku)           => req(`/productos/${sku}`, { method: "DELETE" })

// Forecast tabla pivot
export const getForecastTabla = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast/tabla${q ? '?' + q : ''}`)
}
export const upsertForecastMes = (sku, anio, mes, cantidad) =>
  req('/forecast/bulk-upsert', {
    method: 'POST',
    body: JSON.stringify([{ sku, anio, mes, cantidad }])
  })

// Carga Excel Forecast
export const cargaForecastExcel = async (file, anio = 2026) => {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/forecast/carga-excel?anio=${anio}`, {
    method: "POST",
    body: form,
    headers: { "Authorization": `Bearer ${getToken()}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Error al procesar el Excel")
  }
  return res.json()
}

// Ajuste Forecast
export const getProyeccion = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/ajuste-forecast/proyeccion${q ? '?' + q : ''}`)
}
export const aplicarProyeccion = (items) =>
  req('/ajuste-forecast/aplicar-proyeccion', { method: 'POST', body: JSON.stringify(items) })
export const getAlertasQuiebre = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/ajuste-forecast/alertas-quiebre${q ? '?' + q : ''}`)
}

// ── Forecast Dinámico ────────────────────────────────────────────────────────
export const getForecastResumen = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast-dinamico/resumen${q ? '?' + q : ''}`)
}
export const getForecastSku = (sku, meses = 6) =>
  req(`/forecast-dinamico/sku/${sku}?meses=${meses}`)
export const calcularForecast = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast-dinamico/calcular${q ? '?' + q : ''}`, { method: 'POST' })
}
export const getLiftFactors = (vigente = false) =>
  req(`/forecast-dinamico/lift-factors${vigente ? '?vigente=true' : ''}`)
export const crearLiftFactor = (data) =>
  req('/forecast-dinamico/lift-factors', { method: 'POST', body: JSON.stringify(data) })
export const actualizarLiftFactor = (id, data) =>
  req(`/forecast-dinamico/lift-factors/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const eliminarLiftFactor = (id) =>
  req(`/forecast-dinamico/lift-factors/${id}`, { method: 'DELETE' })
export const getAlertasForecast = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast-dinamico/alertas${q ? '?' + q : ''}`)
}
export const resolverAlertaForecast = (id) =>
  req(`/forecast-dinamico/alertas/${id}/resolver`, { method: 'PATCH', body: JSON.stringify({}) })
export const getSegmentacion = (canal) =>
  req(`/forecast-dinamico/segmentacion${canal ? '?canal=' + encodeURIComponent(canal) : ''}`)
export const recalcularSegmentacion = (periodoInicio, periodoFin) =>
  req(`/forecast-dinamico/segmentacion/recalcular?periodo_inicio=${periodoInicio}&periodo_fin=${periodoFin}`, { method: 'POST' })
export const getOrdenesSugeridas = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast-dinamico/ordenes-compra${q ? '?' + q : ''}`)
}
export const refreshVistaForecast = () =>
  req('/forecast-dinamico/refresh-vista', { method: 'POST' })
export const getOverrides = (params = {}) => {
  const q = new URLSearchParams(params).toString()
  return req(`/forecast-dinamico/overrides${q ? '?' + q : ''}`)
}
export const crearOverride = (data) =>
  req('/forecast-dinamico/overrides', { method: 'POST', body: JSON.stringify(data) })
export const eliminarOverride = (id) =>
  req(`/forecast-dinamico/overrides/${id}`, { method: 'DELETE' })

export const cargaMasivaProductos = async (file, modo = "upsert") => {
  const form = new FormData()
  form.append("file", file)
  form.append("modo", modo)
  const res = await fetch(`${BASE}/productos/carga-masiva`, {
    method: "POST",
    body: form,
    headers: { "Authorization": `Bearer ${getToken()}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || "Error en carga masiva")
  }
  return res.json()
}
