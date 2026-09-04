@echo off
setlocal
set "APP_DIR=%~dp0"
set "EXE_PATH=%APP_DIR%Kiara.exe"

if exist "%~dp0..\app\ui\desktop.py" (
    for %%S in ("%~dp0..\app\ui\desktop.py") do set "SOURCE_TIME=%%~tS"
    for %%E in ("%EXE_PATH%") do set "EXE_TIME=%%~tE"
)

if not exist "%EXE_PATH%" (
    echo Kiara.exe not found in %APP_DIR%
    exit /b 1
)

echo Iniciando Kiara SDR (%EXE_TIME%).

start "Kiara" "%EXE_PATH%"
exit /b 0
