@echo off
rem DrakoTV - crea el instalador (.exe) para Windows en la carpeta dist\
cd /d "%~dp0"
title DrakoTV - crear instalador
where node >nul 2>nul || (echo Falta Node.js: https://nodejs.org & pause & exit /b 1)
call npm install
if errorlevel 1 goto error
call npm run dist
if errorlevel 1 goto error
echo.
echo  Listo. El instalador y la version portable estan en la carpeta "dist".
start "" dist
pause
exit /b 0
:error
echo  No se pudo crear el instalador.
pause
exit /b 1
