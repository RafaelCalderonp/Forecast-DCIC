# Informe Técnico — Requerimientos API de Ventas DCIC
**Fecha:** 19 de junio de 2026  
**Solicitante:** Rafael Calderón — rafael.calderon@dcic.cl  
**Sistema:** Forecast ERP DCIC (FastAPI + PostgreSQL)

---

## 1. Contexto

Importadora DCIC utiliza la API (`https://dcic-api-production.up.railway.app/ventas`) para sincronizar ventas desde Bsale y Wivo hacia su sistema interno de forecasting y análisis de márgenes.

Al comparar los datos de la API con el reporte Excel de ventas (2024–2026), detectamos una **brecha significativa**:

| Fuente | Filas Regular | Cobertura |
|--------|--------------|-----------|
| Excel (fuente oficial) | 314.361 | 100% |
| API (acumulado importado) | ~158.755 | ~50% |

Esta diferencia impacta directamente el cálculo de forecasts, márgenes y KPIs del negocio.

---

## 2. Problemas Detectados

### 2.1 Cobertura incompleta de transacciones

La API entrega aproximadamente el **50% de las líneas de venta** que aparecen en los reportes de Bsale/Wivo exportados a Excel. No es un problema de paginación (el script pagina correctamente usando `limit`/`offset` y verifica `X-Returned-Count`).

**Hipótesis:** La API filtra o agrega transacciones antes de exponerlas, o ciertas combinaciones de canal/fecha no están accesibles mediante los filtros disponibles.

### 2.2 Canales no expuestos por la API

Los siguientes canales aparecen en el Excel pero **nunca** en los datos de la API:

| Canal | Filas en Excel |
|-------|---------------|
| Petwoow | 2.536 |
| Segunda Seleccion | 724 |
| Dafiti | 224 |
| Pérgolas | 235 |
| Cta cte Personal | 356 |

Necesitamos que estos canales sean **incluidos en el endpoint `/ventas`**.

### 2.3 Campos faltantes o mal calculados

Campos presentes en el Excel que **no están disponibles** en la respuesta de la API:

| Campo Excel | Campo API actual | Estado |
|-------------|-----------------|--------|
| `N° Pedido` | no disponible | **Faltante** |
| `N° Sub-Orden` | no disponible | **Faltante** |
| `Margen CLP` | `margen_clp` | Disponible pero valores difieren |
| `Margen %` | `margen_pct` | Disponible pero valores difieren |
| `Costo Calc.` | `costo_unitario_neto` | Disponible |
| `Tipo Registro` | `tipo_linea` | Disponible |
| `Estado de Despacho` | `estado_despacho` | Disponible |

---

## 3. Requerimientos Solicitados

### R1 — Endpoint `/ventas` con cobertura completa (CRÍTICO)

El endpoint debe retornar **todas** las líneas de venta disponibles en Bsale y Wivo, sin filtros internos que excluyan transacciones.

**Parámetros de filtro requeridos (ya existentes, confirmar funcionamiento):**

```
GET /ventas?fecha_desde=YYYY-MM-DD&fecha_hasta=YYYY-MM-DD&fuente=bsale|wivo&limit=100&offset=0
```

**Comportamiento esperado:**
- El total de registros retornados debe coincidir con los exportables desde Bsale/Wivo para el mismo rango de fechas
- `X-Total-Count` (o equivalente) en headers para conocer el total antes de paginar
- Soporte para `estado_orden=Regular,Devuelta` (actualmente solo filtra Regular en algunos casos)

### R2 — Incluir campos de número de pedido (CRÍTICO)

Agregar a la respuesta de cada registro:

```json
{
  "num_pedido":   "123456",     // N° Pedido del sistema de origen
  "num_suborden": "123456-1"    // N° Sub-Orden (si aplica)
}
```

Estos campos son necesarios para **deduplicar correctamente** las líneas de venta y evitar que una misma transacción se inserte dos veces.

### R3 — Incluir todos los canales de venta

Confirmar que los siguientes canales estén disponibles en el endpoint:
- Petwoow
- Segunda Seleccion  
- Dafiti
- Pérgolas
- Cta cte Personal

Si no están en la API porque son canales distintos de Bsale/Wivo, indicar qué endpoint o sistema los expone.

### R4 — Header con total de registros

Para cada consulta paginada, incluir en los headers HTTP:

```
X-Total-Count: 5423       # total de registros que coinciden con el filtro
X-Returned-Count: 100     # registros en esta página
X-Limit: 100
X-Offset: 0
```

Actualmente solo existe `X-Returned-Count` y `X-Limit`. Sin `X-Total-Count` no podemos saber si la paginación está completa.

### R5 — Endpoint de estado de sincronización (deseable)

Un endpoint que indique la última fecha disponible de datos por fuente:

```
GET /ventas/status
→ {
    "bsale": { "ultima_fecha": "2026-06-14", "total_registros": 180000 },
    "wivo":  { "ultima_fecha": "2026-06-14", "total_registros": 95000  }
  }
```

---

## 4. Estructura de Campos Esperada por Registro

```json
{
  "sku_id":              "ABC-123",
  "fecha":               "2024-03-15",
  "canal":               "Mercado Libre",
  "fuente":              "bsale",
  "estado_orden":        "Regular",
  "estado_despacho":     "Entregado",
  "tipo_linea":          "Venta",
  "cantidad":            2,
  "venta_bruto":         29990,
  "valor_unitario_bruto":14995,
  "costo_unitario_neto": 8000,
  "margen_clp":          6995,
  "margen_pct":          46.6,
  "desc_producto":       "Pelota de Tenis...",
  "categoria_producto":  "Tenis",
  "marca_producto":      "Wilson",
  "num_pedido":          "2024031500123",
  "num_suborden":        "2024031500123-1"
}
```

---

## 5. Impacto del Problema

- El sistema de forecasting proyecta demanda 2027 basado en ventas 2024–2026. Con solo el 50% de los datos, las proyecciones subestiman la demanda real en ~50%.
- Los márgenes calculados son incorrectos porque el volumen de venta está incompleto.
- El KPI de "Venta Bruta" visible en el ERP muestra ~$640M para diciembre 2024, cuando la realidad fue >$1.000M.

---

## 6. Solución Transitoria Implementada

Mientras se resuelven los puntos anteriores, hemos implementado una importación directa desde el Excel de exportación de Bsale/Wivo (`2024-2026.xlsx`) como fuente de verdad. La API seguirá usándose para actualizaciones incrementales desde la fecha del Excel en adelante.

Para esto se requiere que **la API esté disponible y actualizada** para cubrir fechas posteriores al 14 de junio de 2026.

---

## 7. Contacto

Rafael Calderón — rafael.calderon@dcic.cl  
Sistema: `https://dcic-api-production.up.railway.app`
