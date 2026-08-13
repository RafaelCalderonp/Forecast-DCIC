# API de stock — dcic-stock-loader

Servicio que consolida el stock de DCIC en una sola tabla y lo expone por HTTP. Junta en
un lugar cosas que viven en cuatro sistemas distintos: las bodegas de Bsale, el
fulfillment de MercadoLibre, el de Falabella y las órdenes de compra de DCIC IQ.

**Base:** `https://dcic-stock-loader-production.up.railway.app`

Quien pregunte por stock debería preguntarle a este servicio y no a Bsale directo: acá
el dato ya viene con el criterio de negocio aplicado (qué bodega es vendible, cuál es
tránsito, cuál ni se carga) y con el espejo del Full de MeLi al día, que en Bsale queda
viejo.

---

## Autenticación

Todos los endpoints de consulta piden el header `X-API-Key`:

```bash
curl -H "X-API-Key: $STOCK_API_KEY" \
     "https://dcic-stock-loader-production.up.railway.app/api/stock"
```

| Respuesta | Qué pasó |
|---|---|
| `401` | La clave no coincide. |
| `503` | El servicio no tiene clave configurada. Falla cerrado: sin `STOCK_API_KEY` no atiende a nadie, en vez de quedar abierto. |

---

## Cada cuánto se actualiza

El servicio recarga **solo, cada 60 minutos** (`STOCK_AUTO_INTERVAL_MIN`), y también al
arrancar. No hay que dispararle nada: los endpoints leen la tabla, así que responden
igual de rápido durante una carga.

El campo `actualizado` de la respuesta dice cuándo terminó la última carga completa
(ISO 8601). Viene en `null` si el servicio arrancó recién y todavía no terminó ninguna.

---

## Las bodegas

| ID | Nombre | Qué es | De dónde sale |
|---:|---|---|---|
| **10** | Ecommerce/Marketplaces | **La bodega principal.** Lo que está físicamente en DCIC y se puede vender hoy. | API de Bsale |
| **3** | Bodegas Full MeLi | Stock ya enviado al fulfillment de MercadoLibre. Se vende, pero no está en DCIC. | API de dcic-int-ml |
| **4** | Bodegas Full Falabella | Lo mismo para el fulfillment de Falabella. | API de Falabella Seller |
| **2** | Importaciones en Tránsito | Mercadería comprada que **ya zarpó** y todavía no entra a bodega. No se puede vender. | API de Bsale |
| **101** | Proforma | Mercadería comprada que **todavía no zarpa**: órdenes de compra que el proveedor ya aceptó. Trae fecha de llegada comprometida. | dcic-iq-product-back |
| 1 | Bodegas Full | Bodega antigua. **Nadie la escribe hoy**, siempre viene en 0. Se devuelve solo porque existe en la tabla. | — |

La **Bodega Segunda** (mercadería con falla) no se carga a propósito: no es stock
vendible y sumarla infla el disponible.

### Cómo sumar según la pregunta

| Pregunta | Suma |
|---|---|
| ¿Cuánto puedo vender hoy? | `10 + 3 + 4` |
| ¿Cuánto viene en camino? | `2 + 101` |
| ¿Cuánto tengo comprometido en total? | `10 + 3 + 4 + 2 + 101` |

**Las bodegas 2 y 101 no se pisan entre sí.** Una orden está en la 101 hasta que zarpa;
en cuanto zarpa sale de la 101 y aparece en la 2. Por eso se pueden sumar sin contar dos
veces la misma caja.

### Qué cuenta como Proforma (bodega 101)

Lo decide dcic-iq-product-back, no este servicio:

- La orden está en `compra_aceptada` o `en_ejecucion` — es decir, **el proveedor ya firmó
  el acuse de la Invoice**. Antes de esa firma la compra todavía se puede caer.
- La orden **no ha zarpado**. Se considera zarpada si tiene el hito "Embarcada (BL)", o si
  va en un embarque enviado con B/L aunque nadie haya estampado el hito.
- Se descuentan las unidades ya recibidas.

La **fecha de llegada** es la comprometida en la orden. Una orden sin fecha puesta viaja
con `eta: null`: las unidades igual cuentan. `eta: null` con la bodega 101 en 0 significa
otra cosa —que no hay nada por llegar— y la diferencia se ve mirando la 101.

---

## `GET /api/stock` — el consolidado

Para quien quiere la respuesta ya masticada: qué hay disponible y qué viene en tránsito.

**Parámetros**

| Nombre | Tipo | Default | Qué hace |
|---|---|---|---|
| `skus` | string | — | Filtra por SKUs, separados por coma. Sin esto vienen todos. |
| `incluir_transito` | bool | `true` | Incluye la bodega 2 en la respuesta. |

**Respuesta**

```json
{
  "ok": true,
  "n": 432,
  "bodegas_disponible": [10, 3, 4],
  "bodega_transito": 2,
  "actualizado": "2026-08-13T15:40:12",
  "stock": {
    "R2994": {
      "available": 57,
      "transit": 0,
      "cost": 12450.0,
      "by_bodega": { "10": 45, "3": 12, "4": 0 }
    }
  }
}
```

| Campo | Qué es |
|---|---|
| `available` | Suma de las bodegas vendibles: `10 + 3 + 4`. |
| `transit` | Bodega 2. Informativo: no es vendible. |
| `cost` | Costo unitario neto conocido, en pesos. `null` si no hay. |
| `by_bodega` | El desglose crudo que produjo esos totales. |

> Este endpoint **no incluye la proforma**. Para eso está el de abajo.

---

## `GET /api/stock/por-bodega` — el detalle

Cada SKU con **todas** las bodegas y su fecha de llegada. La bodega sin registro va en 0,
no se omite: la forma de la respuesta es siempre la misma y no hay que preguntarse si un
0 es "cero unidades" o "no vino el dato".

**Parámetros**

| Nombre | Tipo | Default | Qué hace |
|---|---|---|---|
| `skus` | string | — | Filtra por SKUs, separados por coma. |
| `solo_con_stock` | bool | `true` | Devuelve solo los SKUs con al menos una bodega en positivo. En `false` vienen todos, incluidos los que están en cero en todo (que son la mayoría del maestro). |
| `incluir_lotes` | bool | `false` | Agrega el desglose de la proforma: cada llegada con su cantidad y su fecha. |

**Respuesta**

```json
{
  "ok": true,
  "n": 432,
  "actualizado": "2026-08-13T15:40:12",
  "bodegas": [
    { "id": 1,   "nombre": "Bodegas Full" },
    { "id": 2,   "nombre": "Bodega Importaciones en Tránsito" },
    { "id": 3,   "nombre": "Bodegas Full MeLi" },
    { "id": 4,   "nombre": "Bodegas Full Falabella" },
    { "id": 10,  "nombre": "Ecommerce/Marketplaces" },
    { "id": 101, "nombre": "Proforma" }
  ],
  "solo_con_stock": true,
  "stock": {
    "R2994": {
      "bodegas": { "1": 0, "2": 0, "3": 12, "4": 0, "10": 45, "101": 400 },
      "total": 457,
      "eta": "2026-10-15"
    }
  }
}
```

| Campo | Qué es |
|---|---|
| `bodegas` | Las bodegas que existen, con su nombre. Sirve para no tener los IDs escritos a mano. |
| `stock[sku].bodegas` | Unidades por bodega. Las claves son los IDs **como string** (así vienen en JSON). |
| `stock[sku].total` | Suma de todas las bodegas, proforma incluida. Si necesitas otro corte, súmalo tú desde `bodegas`. |
| `stock[sku].eta` | Cuándo empieza a llegar lo de la proforma: la fecha comprometida más temprana. `null` si no hay proforma pendiente, o si la hay pero ninguna orden tiene fecha. |

Con `incluir_lotes=true`, cada SKU trae además:

```json
"lotes": [
  { "unidades": 300, "eta": "2026-10-15" },
  { "unidades": 100, "eta": "2026-12-01" }
]
```

Un lote es **una orden de compra**. El mismo SKU puede venir en dos órdenes que llegan en
meses distintos: por eso son dos lotes y no un número con una sola fecha. Las llegadas sin
fecha van al final de la lista.

---

## Ejemplos

**Tres SKUs, con el desglose de llegadas**

```bash
curl -H "X-API-Key: $STOCK_API_KEY" \
  "$BASE/api/stock/por-bodega?skus=R2994,R6054,R1017&incluir_lotes=true"
```

**Python — armar la tabla de productos (stock vendible, en camino y fecha)**

```python
import requests

BASE = "https://dcic-stock-loader-production.up.railway.app"
r = requests.get(f"{BASE}/api/stock/por-bodega",
                 headers={"X-API-Key": STOCK_API_KEY}, timeout=60)
r.raise_for_status()
data = r.json()

VENDIBLES = ("10", "3", "4")
for sku, fila in data["stock"].items():
    b = fila["bodegas"]
    vendible = sum(b[i] for i in VENDIBLES)
    en_camino = b["2"] + b["101"]
    print(f"{sku}: {vendible} vendibles · {en_camino} en camino · llega {fila['eta'] or 'sin fecha'}")
```

---

## Cosas que conviene saber

- **Un SKU que no aparece no es un SKU en cero.** Por defecto (`solo_con_stock=true`) se
  omiten los que están en cero en todas las bodegas. Si necesitas la lista completa del
  maestro, pide `solo_con_stock=false`.
- **Los SKUs que no existen en el maestro (`dcic_operations_producto`) se ignoran** al
  cargar. Si una orden de compra trae un SKU que nunca se dio de alta, sus unidades no van
  a aparecer acá; la carga lo registra en el log.
- **Si DCIC IQ no responde**, la bodega 101 se queda con lo de la última carga buena y el
  resto del stock se actualiza igual. Un dato de hace una hora es mejor que un cero, que
  se leería como "no hay nada comprado".
- **La interfaz web** (`/` en el mismo dominio) muestra el estado de la carga automática,
  los logs de la última corrida y permite forzar una.
