@echo off
setlocal
set SCRIPT_DIR=%~dp0

echo Abriendo ventana de Chrome dedicada (modo depuracion)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-chrome-debug.ps1"

timeout /t 3 /nobreak >nul

echo.
echo Iniciando el servidor local (deja esta ventana abierta)...
start "Bsale Bulk - Servidor" cmd /k "cd /d "%SCRIPT_DIR%" && npm start"

timeout /t 3 /nobreak >nul

echo.
echo Abriendo la herramienta...
start "" "http://localhost:4127"

echo.
echo ============================================================
echo  En la ventana de Chrome nueva (perfil dedicado):
echo  1) Si es la primera vez, inicia sesion en Bsale ahi mismo.
echo  2) Entra a "Nuevo consumo".
echo  3) Usa la pestana localhost:4127 para pegar tus datos.
echo ============================================================
pause
