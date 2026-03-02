@echo off
setlocal enableextensions enabledelayedexpansion

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

set "DATA_DIR=%APP_DIR%\data"
set "LOG_DIR=%DATA_DIR%\logs\app"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "LOG_FILE=%LOG_DIR%\launcher_%STAMP%.log"

echo [run_app_windows] %date% %time% starting app from %APP_DIR% > "%LOG_FILE%"
cd /d "%APP_DIR%"
python app.py >> "%LOG_FILE%" 2>&1
endlocal
