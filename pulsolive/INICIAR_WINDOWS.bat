@echo off
rem PulsoLive - arranque con doble clic en Windows.
rem La primera vez instala todo (tarda unos minutos). Despues solo abre la app.
cd /d "%~dp0"
title PulsoLive
echo.
echo  ===============================
echo            PulsoLive
echo  ===============================
echo.

rem --- 1. Buscar Python ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto nopython

rem --- 2. Primera vez: entorno e instalacion ---
if not exist ".venv\Scripts\python.exe" (
  echo Preparando PulsoLive por primera vez, espera unos minutos...
  %PY% -m venv .venv
  if errorlevel 1 goto error
)
set "VPY=.venv\Scripts\python.exe"
if not exist ".venv\instalado.txt" (
  echo Instalando componentes...
  "%VPY%" -m pip install --upgrade pip
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 goto error
  echo ok> ".venv\instalado.txt"
)
if not exist ".env" copy ".env.example" ".env" >nul

rem --- 3. Base de datos y cuenta demo ---
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto error
"%VPY%" manage.py seed_demo
if errorlevel 1 goto error

rem --- 4. Abrir la app ---
echo.
echo  Listo. Se abrira el navegador en http://localhost:8000
echo  Cuenta demo:  demo@pulsolive.app  /  demo12345
echo  Para apagar PulsoLive cierra esta ventana.
echo.
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
"%VPY%" manage.py runserver
goto fin

:nopython
echo  No encontre Python en esta computadora.
echo.
echo  1. Se abrira la pagina de descarga: baja Python e instalalo.
echo  2. IMPORTANTE: en la primera pantalla marca "Add python.exe to PATH".
echo  3. Cuando termine, vuelve a dar doble clic a este archivo.
echo.
start "" https://www.python.org/downloads/
pause
goto fin

:error
echo.
echo  Algo fallo. Toma una foto de esta ventana y mandala para revisarlo.
pause

:fin
