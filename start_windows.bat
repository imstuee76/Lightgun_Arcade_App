@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File update_lightgun_app_windows.ps1
endlocal
