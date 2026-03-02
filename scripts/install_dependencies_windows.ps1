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

function Resolve-PythonCommand {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        & py -3 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return @("py", "-3")
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        & python --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return @("python")
        }
    }

    return @()
}

function Invoke-Checked {
    param(
        [string[]]$Command,
        [string]$ErrorMessage
    )
    if (-not $Command -or $Command.Count -eq 0) {
        throw "Internal error: empty command invocation."
    }
    & $Command[0] $Command[1..($Command.Count - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

Write-Host "[deps-win] checking python runtime"
$pythonRunner = Resolve-PythonCommand
if (-not $pythonRunner -or $pythonRunner.Count -eq 0) {
    Write-Host "[deps-win] python runtime missing, attempting install via winget"
    $installed = Ensure-WingetPackage -WingetId "Python.Python.3.12"
    if (-not $installed) {
        throw "Python runtime is required. Install Python 3 and re-run."
    }

    $env:Path += ";$env:LocalAppData\Programs\Python\Python312;$env:LocalAppData\Programs\Python\Python312\Scripts"
    $pythonRunner = Resolve-PythonCommand
    if (-not $pythonRunner -or $pythonRunner.Count -eq 0) {
        throw "Python install attempted but runtime is still unavailable. Open a new terminal and run updater again."
    }
}

Write-Host "[deps-win] using python runner: $($pythonRunner -join ' ')"

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
$pipUpgrade = @($pythonRunner + @("-m", "pip", "install", "--upgrade", "pip"))
Invoke-Checked -Command $pipUpgrade -ErrorMessage "Failed to upgrade pip."

$pipInstall = @($pythonRunner + @("-m", "pip", "install", "-r", "$AppDir\requirements.txt"))
Invoke-Checked -Command $pipInstall -ErrorMessage "Failed to install Python requirements."

Write-Host "[deps-win] completed"
