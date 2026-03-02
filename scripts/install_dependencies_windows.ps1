$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir

function Ensure-WingetPackage {
    param(
        [string]$WingetId
    )
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "[deps-win] winget missing, cannot auto-install $WingetId"
        return $false
    }
    winget install --id $WingetId -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    return $true
}

Write-Host "[deps-win] checking python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[deps-win] python missing, attempting install via winget"
    $installed = Ensure-WingetPackage -WingetId "Python.Python.3.12"
    if (-not $installed) {
        throw "Python is required. Install Python 3 and re-run."
    }
    $env:Path += ";$env:LocalAppData\Programs\Python\Python312;$env:LocalAppData\Programs\Python\Python312\Scripts"
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python install attempted but python command is still unavailable. Open a new terminal and run again."
    }
}

Write-Host "[deps-win] checking git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[deps-win] installing Git via winget"
    if (-not (Ensure-WingetPackage -WingetId "Git.Git")) {
        Write-Host "[deps-win] winget not found; install Git manually from https://git-scm.com/download/win"
    }
}

Write-Host "[deps-win] checking fceux"
if (-not (Get-Command fceux -ErrorAction SilentlyContinue) -and -not (Get-Command fceux.exe -ErrorAction SilentlyContinue)) {
    Write-Host "[deps-win] installing FCEUX via winget"
    if (-not (Ensure-WingetPackage -WingetId "FCEUX.FCEUX")) {
        Write-Host "[deps-win] winget not found; install FCEUX manually from https://fceux.com/web/download.html"
    }
}

Write-Host "[deps-win] installing python packages"
python -m pip install --upgrade pip | Out-Null
python -m pip install -r "$AppDir\requirements.txt"

Write-Host "[deps-win] completed"
