# Abre una ventana de Chrome nueva y separada, con el puerto de depuracion remota
# habilitado, usando un perfil propio (no tu perfil normal).
#
# No cierra tus ventanas de Chrome actuales: esta ventana es independiente.
# La primera vez, tendras que iniciar sesion en Bsale dentro de ESTA ventana
# (la sesion se guarda en el perfil dedicado y quedara iniciada la proxima vez).

$ErrorActionPreference = "Stop"

$candidatePaths = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chromePath = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chromePath) {
  Write-Host "No se encontro chrome.exe en las rutas conocidas. Edita este script y ajusta la ruta." -ForegroundColor Red
  exit 1
}

# Nota: Chrome bloquea el puerto de depuracion si --user-data-dir apunta al perfil
# por defecto real (medida de seguridad). Por eso usamos un perfil dedicado aparte.
$profileDir = "$env:LOCALAPPDATA\BsaleBulkChromeProfile"

# Si ya hay una ventana de este perfil dedicado corriendo con el puerto abierto, no abrir otra.
try {
  Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 2 | Out-Null
  Write-Host "Ya hay una ventana de Chrome en modo depuracion corriendo. No se abre otra." -ForegroundColor Yellow
  exit 0
} catch {
  # no esta corriendo, seguimos
}

Write-Host "Abriendo Chrome (perfil dedicado) con depuracion remota en el puerto 9222..." -ForegroundColor Green
Start-Process -FilePath $chromePath -ArgumentList @(
  "--remote-debugging-port=9222",
  "--user-data-dir=`"$profileDir`""
)

Write-Host "Listo. En ESA ventana: si es la primera vez, inicia sesion en Bsale." -ForegroundColor Green
