$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
$Desktop = [Environment]::GetFolderPath("Desktop")

$RunShortcut = Join-Path $Desktop "Lightgun Arcade App.bat"
$UpdateShortcut = Join-Path $Desktop "Lightgun Arcade Updater.bat"
$FullInstallShortcut = Join-Path $Desktop "Lightgun Arcade Full Install.bat"

Set-Content -Path $RunShortcut -Encoding ASCII -Value @"
@echo off
cd /d "$AppDir"
call run_app_windows.bat
"@

Set-Content -Path $UpdateShortcut -Encoding ASCII -Value @"
@echo off
cd /d "$AppDir"
powershell -NoProfile -ExecutionPolicy Bypass -File update_lightgun_app_windows.ps1
"@

Set-Content -Path $FullInstallShortcut -Encoding ASCII -Value @"
@echo off
cd /d "$AppDir"
call full_install_windows.bat
"@

Write-Host "[desktop-win] created: $RunShortcut"
Write-Host "[desktop-win] created: $UpdateShortcut"
Write-Host "[desktop-win] created: $FullInstallShortcut"
