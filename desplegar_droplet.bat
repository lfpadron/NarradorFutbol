@echo off
setlocal EnableExtensions
title Desplegar Narrador de Futbol

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0desplegar_droplet.ps1"
set "DEPLOY_EXIT_CODE=%ERRORLEVEL%"

echo.
if "%DEPLOY_EXIT_CODE%"=="0" (
    echo [EXITO] Despliegue terminado correctamente.
) else (
    echo [ERROR] El despliegue termino con codigo %DEPLOY_EXIT_CODE%.
    echo El mensaje de error se muestra arriba. La actualizacion no se completo correctamente.
)
echo.
echo Pulsa cualquier tecla para cerrar esta ventana...
pause >nul
exit /b %DEPLOY_EXIT_CODE%
