@echo off
rem Sala de edicion: instala en esta compu el programa que edita los videos de tu oficina.
rem Doble clic y sigue las instrucciones. Se puede correr otra vez para actualizar o volver a dar de alta.
chcp 65001 >nul
title Sala de edicion - instalador
echo.
echo   Bajando el instalador de la Sala de edicion...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://raw.githubusercontent.com/DR4k3RM4N/DR4k3RM4N/claude/keen-johnson-v42a39/salaedicion/windows/instalar.ps1'; $f=Join-Path $env:TEMP 'instalar_sala.ps1'; Invoke-WebRequest -UseBasicParsing $u -OutFile $f; & $f"
echo.
pause
