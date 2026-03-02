@echo off
setlocal
cd /d "%~dp0"

echo [full-install-win] Running updater (no launch)...
powershell -NoProfile -ExecutionPolicy Bypass -File update_lightgun_app_windows.ps1 -NoLaunch
if errorlevel 1 (
  echo [full-install-win] updater failed
  exit /b 1
)

echo [full-install-win] Ensuring support files...
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\download_support_files_windows.ps1
if errorlevel 1 (
  echo [full-install-win] support file download failed
  exit /b 1
)

echo [full-install-win] Launching app...
call run_app_windows.bat

endlocal
