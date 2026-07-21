// ── Constantes y utilidades puras de TablaForecast ──────────────────────────

// Q4 2026: meses con proyección modelo ANCLA-SI-MACRO
export const Q4_MESES = [9, 10, 11] // índices 0-based: Oct=9, Nov=10, Dic=11

export const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
export const ANIO  = 2026

// Formateadores CLP
export const clp  = n => n == null ? '—' : Math.round(n).toLocaleString('es-CL')
export const mclp = n => n == null ? '—' : Math.round(n).toLocaleString('es-CL')

// Columnas fijas izquierda y sus anchos (px)
export const COLS_FIJAS = [
  { key: 'marca',         label: 'Marca',            w: 72  },
  { key: 'sku',           label: 'SKU',              w: 72  },
  { key: 'descripcion',   label: 'Descripción',      w: 200 },
  { key: 'subcategoria',  label: 'Subcategoría',     w: 120 },
  { key: 'tipo_producto', label: 'Tipo de Producto', w: 120 },
  { key: 'temporada',     label: 'Temporada',        w: 90  },
]

export const LEFT_OFFSETS = COLS_FIJAS.reduce((acc, col, i) => {
  acc[i] = i === 0 ? 0 : acc[i - 1] + COLS_FIJAS[i - 1].w
  return acc
}, {})

export const TOTAL_FROZEN = COLS_FIJAS.reduce((s, c) => s + c.w, 0)

// Períodos disponibles para exportar a Excel
export const PERIODOS = [
  { val: 'm0',  label: 'Ene' }, { val: 'm1',  label: 'Feb' }, { val: 'm2',  label: 'Mar' },
  { val: 'm3',  label: 'Abr' }, { val: 'm4',  label: 'May' }, { val: 'm5',  label: 'Jun' },
  { val: 'm6',  label: 'Jul' }, { val: 'm7',  label: 'Ago' }, { val: 'm8',  label: 'Sep' },
  { val: 'm9',  label: 'Oct' }, { val: 'm10', label: 'Nov' }, { val: 'm11', label: 'Dic' },
  { val: 'q1',  label: 'Q1 Ene–Mar' }, { val: 'q2', label: 'Q2 Abr–Jun' },
  { val: 'q3',  label: 'Q3 Jul–Sep' }, { val: 'q4', label: 'Q4 Oct–Dic' },
  { val: 'todo', label: 'Año completo' },
]

// Mapa quarter → índices de mes
export const MESES_Q = {
  todo: null,
  q1: [0,1,2], q2: [3,4,5], q3: [6,7,8], q4: [9,10,11],
  m9: [9], m10: [10], m11: [11],
}
