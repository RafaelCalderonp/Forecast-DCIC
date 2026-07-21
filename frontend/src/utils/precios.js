// src/utils/precios.js

/**
 * Redondea precio bruto a 2 decimales
 */
export function redondearBruto(valor) {
  const n = parseFloat(valor)
  if (isNaN(n)) return ""
  return Math.round(n * 100) / 100
}

/**
 * Calcula precio neto = round(bruto / 1.19, 2)
 */
export function calcularNeto(bruto) {
  const n = parseFloat(bruto)
  if (isNaN(n) || n <= 0) return ""
  return Math.round((n / 1.19) * 100) / 100
}

/**
 * Formatea número como moneda CLP
 */
export function formatCLP(valor) {
  if (valor === "" || valor === null || valor === undefined) return "—"
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valor)
}
