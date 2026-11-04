@echo off
rem DrakoTV - abrir con doble clic en Windows.
rem La primera vez descarga los componentes (unos minutos). Despues abre directo.
cd /d "%~dp0"
title DrakoTV
where node >nul 2>nul || goto nonode
if not exist "node_modules\electron\dist\electron.exe" (
  echo Preparando DrakoTV por primera vez, espera unos minutos...
  call npm install
  if errorlevel 1 goto error
)
start "" "node_modules\electron\dist\electron.exe" .
exit /b 0
:nonode
echo.
echo  Falta Node.js. Descargalo de https://nodejs.org (version LTS), instalalo
echo  y vuelve a abrir este archivo.
start https://nodejs.org/es/download
pause
exit /b 1
:error
echo.
echo  Algo fallo durante la instalacion. Revisa tu conexion a internet e intenta de nuevo.
pause
exit /b 1
