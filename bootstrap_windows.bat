@echo off
setlocal enableextensions

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
if not exist "%APP_DIR%\bootstrap_windows.ps1" (
  echo [bootstrap-win] Missing bootstrap_windows.ps1 in %APP_DIR%
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\bootstrap_windows.ps1"
if errorlevel 1 (
  echo [bootstrap-win] bootstrap failed. Check bootstrap_windows_*.log in %APP_DIR%
  pause
  exit /b 1
)
endlocal
