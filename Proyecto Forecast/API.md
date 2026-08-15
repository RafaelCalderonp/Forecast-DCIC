# API de stock — dcic-stock-loader

Servicio que consolida el stock de DCIC en una sola tabla y lo expone por HTTP. Junta en
un lugar cosas que viven en cuatro sistemas distintos: las bodegas de Bsale, el
fulfillment de MercadoLibre, el de Falabella y las órdenes de compra de DCIC IQ.

**Base:** `https://dcic-stock-loader-production.up.railway.app`

> Esta es la **referencia**: qué endpoints hay y qué significa cada campo. Si lo que
> buscas es cómo resolver algo concreto —armar la tabla de productos, saber qué reponer,
> entender por qué un número no cuadra— parte por la [guía de uso](GUIA.md).

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
| **2** | Importaciones en Tránsito | Lo que Bsale registra como tránsito. Es de uso escaso: para saber qué viene en camino, mira la 101 y la 102. | API de Bsale |
| **101** | Proforma | Comprado y aceptado por el proveedor, **todavía sin zarpar**. Sigue en fábrica o esperando embarque. Trae fecha de llegada. | dcic-iq-product-back |
| **102** | En tránsito · órdenes | Comprado que **ya salió de origen** y todavía no entra a bodega. Su fecha la manda la naviera cuando hay B/L rastreado. | dcic-iq-product-back |
| 1 | Bodegas Full | Bodega antigua. **Nadie la escribe hoy**, siempre viene en 0. Se devuelve solo porque existe en la tabla. | — |

La **Bodega Segunda** (mercadería con falla) no se carga a propósito: no es stock
vendible y sumarla infla el disponible.

### Cómo sumar según la pregunta

| Pregunta | Suma |
|---|---|
| ¿Cuánto puedo vender hoy? | `10 + 3 + 4` |
| ¿Cuánto viene en camino? | `101 + 102` — o el campo `por_llegar`, que ya lo suma |
| ¿Cuánto tengo comprometido en total? | `10 + 3 + 4 + 101 + 102` |

**`por_llegar` (101 + 102) es el mismo número que la columna "En tránsito" de Productos
en DCIC IQ.** Están separadas porque no son lo mismo: lo que sigue en fábrica puede
correrse meses, lo que ya navega tiene fecha rastreada y llega cuando llega el barco.

**Ojo con la bodega 2**: es la de Bsale y hoy está casi vacía (unos cientos de unidades
en total). Lo que de verdad viene en camino vive en la 101 y la 102, que se calculan
desde las órdenes de compra. Sumar 2 + 102 podría contar dos veces una misma carga.

### Qué cuenta como por llegar (bodegas 101 y 102)

Lo decide dcic-iq-product-back, no este servicio:

- La orden está en `compra_aceptada` o `en_ejecucion` — es decir, **el proveedor ya firmó
  el acuse de la Invoice**. Antes de esa firma la compra todavía se puede caer.
- La orden **no ha llegado**: sin el hito "Recibida" y sin estado `Closed`/`Cancelled`.
- Se descuentan las unidades ya recibidas. Una llegada parcial no borra el saldo: si de
  900 llegaron 10, las 890 que faltan siguen contando.

Lo que decide entre la 101 y la 102 es **si ya zarpó**: cuenta como zarpada la orden con
el hito "Embarcada (BL)", o la que va en un embarque enviado con B/L aunque nadie haya
estampado el hito.

La **fecha de llegada** sale de la **Proforma Invoice**, no de la PO. La PO lleva la
fecha que DCIC pidió; la PI, la que el proveedor respondió, que es la que se va a
cumplir. Muchas veces coinciden —la PI nace copiando la pedida— pero cuando el proveedor
la corre, la buena es la de la PI: la DCMA 202 dice julio en la PO y septiembre en la PI.
La fecha de la PO se usa solo si esa orden todavía no tiene PI cargada.

**Una vez que el barco zarpó, manda la naviera**: para la bodega 102, si hay B/L
rastreado se usa la descarga en puerto (real si ya ocurrió, predicha si no) más 48 horas,
que es la regla de la casa para llegar a bodega. Una promesa escrita meses antes no
compite con un contenedor que se está rastreando.

Una orden sin fecha viaja con `eta: null` y sus unidades cuentan igual. Ojo: `eta: null`
con `por_llegar` en 0 significa otra cosa —que no hay nada por llegar— y la diferencia se
ve mirando ese campo.

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

> Este endpoint **no incluye lo que viene en camino** (bodegas 101 y 102). Para eso está
> el de abajo.

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
| `incluir_lotes` | bool | `false` | Agrega el desglose de la **proforma** (bodega 101): cada llegada con su cantidad y su fecha. No cubre la 102. |

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
    { "id": 101, "nombre": "Proforma" },
    { "id": 102, "nombre": "En tránsito · órdenes" }
  ],
  "solo_con_stock": true,
  "stock": {
    "R2994": {
      "bodegas": { "1": 0, "2": 0, "3": 12, "4": 0, "10": 45, "101": 400, "102": 120 },
      "total": 577,
      "por_llegar": 520,
      "eta": "2026-07-02",
      "eta_por_bodega": { "101": "2026-10-15", "102": "2026-07-02" }
    }
  }
}
```

| Campo | Qué es |
|---|---|
| `bodegas` | Las bodegas que existen, con su nombre. Sirve para no tener los IDs escritos a mano. |
| `stock[sku].bodegas` | Unidades por bodega. Las claves son los IDs **como string** (así vienen en JSON). |
| `stock[sku].total` | Suma de **todas** las bodegas, lo por llegar incluido. Si necesitas otro corte, súmalo tú desde `bodegas`. |
| `stock[sku].por_llegar` | `101 + 102`: lo comprado que todavía no entra a bodega. El número de la columna "En tránsito" de Productos en IQ. |
| `stock[sku].eta` | Cuándo llega lo próximo: la fecha más temprana entre la 101 y la 102. `null` si no hay nada por llegar, o si lo hay pero ninguna orden tiene fecha. |
| `stock[sku].eta_por_bodega` | La fecha de cada una por separado. Sin entrada = esa bodega no tiene fecha. |

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
