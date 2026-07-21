# Carga masiva de consumos en Bsale

Herramienta local para pegar columnas de SKU y Cantidad copiadas de Excel, revisarlas en un
"ticket" por lote de 20, y enviarlas automáticamente al formulario "Nuevo consumo" de Bsale
(búsqueda de producto, selección de la sugerencia, cantidad y "+ Agregar").

## Cómo funciona

- Un servidor local (Node + Playwright) se conecta vía el protocolo de depuración remota (CDP)
  a una ventana de Chrome **dedicada** (perfil propio, separado de tu Chrome normal) y controla
  la pestaña donde tengas Bsale abierto.
- Un frontend (página web local) es donde pegas las columnas, revisas el ticket de cada fila
  y disparas el envío.

> Chrome bloquea la depuración remota si se usa el perfil por defecto real (medida de
> seguridad reciente de Google), así que la herramienta usa un perfil separado dedicado. Esto
> tiene la ventaja de que **no cierra ni toca tu Chrome normal** — es una ventana aparte. Solo
> la primera vez tendrás que iniciar sesión en Bsale dentro de esa ventana dedicada; la sesión
> queda guardada ahí para las próximas veces.

## Instalación (una sola vez)

1. Necesitas Node.js instalado (ya lo tienes: v24).
2. Abre una terminal en esta carpeta (`bsale-bulk`) y corre:
   ```
   npm install
   ```

## Cada vez que quieras usar la herramienta

### Opción rápida (recomendada)

Haz doble clic en **`Iniciar Bsale Bulk.bat`**. Abre una ventana de Chrome dedicada en modo
depuración (no toca tu Chrome normal), inicia el servidor y abre `http://localhost:4127`
automáticamente. Solo te falta, en esa ventana nueva: iniciar sesión en Bsale (primera vez) y
entrar a "Nuevo consumo".

### Opción manual

1. Corre el script `start-chrome-debug.ps1` (clic derecho > "Ejecutar con PowerShell", o desde
   una terminal: `powershell -ExecutionPolicy Bypass -File start-chrome-debug.ps1`). Esto abre
   una ventana de Chrome nueva y separada (perfil dedicado) con el puerto de depuración
   habilitado. Tu Chrome normal sigue intacto.
2. En esa ventana nueva, abre Bsale (inicia sesión si es la primera vez) y entra a la pantalla
   de "Nuevo consumo" (la que muestra "Busca o escanea un producto").
3. En otra terminal, dentro de `bsale-bulk`, corre:
   ```
   npm start
   ```
4. Abre `http://localhost:4127` en una pestaña de esa misma ventana dedicada (o en cualquier
   otro navegador) — el servidor solo necesita ver la pestaña de Bsale dentro de la ventana
   dedicada, no importa desde dónde abras el frontend.

## Uso

1. En "Verificar conexión" confirma que dice conectado y que encontró la pestaña de Bsale.
2. Pega la columna de SKUs (uno por línea) y la columna de Cantidades (una por línea, mismo
   orden) en los dos cuadros, y presiona **Cargar filas**. Puedes cargar más de 20; se van
   guardando en una cola.
3. La tabla muestra el lote actual (hasta 20 filas de la cola). Presiona **Enviar**: la
   herramienta escribe cada SKU en el buscador de Bsale, espera un segundo a que aparezca la
   sugerencia, hace clic sobre ella, escribe la cantidad y hace clic en "+ Agregar", fila por
   fila. El estado de cada fila cambia a "Enviado" o "Error" según el resultado.
4. Revisa manualmente en Bsale que cada línea quedó correcta (primero SKU, luego cantidad).
   Por cada fila que confirmes correcta en Bsale, marca su casilla de **Ticket** en la tabla.
5. Presiona **Validadas**: quita de la cola las filas marcadas con ticket. El lote se rellena
   automáticamente con las siguientes filas pendientes de la cola.
6. Repite Enviar → revisar → Validadas hasta que la cola quede vacía. Cuando queden menos de 20
   filas, el lote simplemente mostrará esas filas restantes.

La cola se guarda en el navegador (localStorage), así que si recargas la página no se pierde el
progreso. **Limpiar todo** la vacía por completo.

## Calibración de selectores (importante antes de usar con 20 filas de una vez)

Los selectores que usa la automatización (`config.json` → `selectors`) están basados en el
texto visible de la pantalla de Bsale que se compartió:

- Buscador: placeholder "Busca o escanea un producto"
- Sugerencia: se busca un elemento que contenga el texto "SKU:<tu-sku>"
- Cantidad: placeholder "Cantidad"
- Botón: texto que contenga "Agregar"

Si tu versión de Bsale tiene textos o comportamiento levemente distintos, la primera fila puede
fallar. Recomendación: **prueba primero con 1 sola fila** cargada, mira lo que hace en la
ventana de Chrome (verás el cursor moverse solo), y si falla revisa el mensaje de error en el
"Registro" del frontend — indica en qué paso se detuvo. Con ese detalle puedo ajustar
`config.json` o `lib/bsale-automation.js` sin tener que rediseñar nada más.

## Notas

- El servidor y el frontend corren solo en tu máquina (`localhost`), no se sube nada a internet.
- Si cierras la ventana dedicada, vuelve a correr `start-chrome-debug.ps1` (o el `.bat`) para
  reabrirla; la sesión de Bsale queda guardada en ese perfil dedicado entre usos.
- Si tienes varias pestañas abiertas dentro de la ventana dedicada, la herramienta busca la que
  contenga "bsale" en la URL; si no la encuentra, usa la última pestaña abierta como respaldo.
