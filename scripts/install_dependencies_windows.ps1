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
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[deps-win] winget install failed for $WingetId (exit $LASTEXITCODE)"
        return $false
    }
    return $true
}

function Get-PythonVersion {
    param(
        [string[]]$Command
    )
    try {
        if (-not $Command -or $Command.Count -eq 0) { return "" }
        $baseArgs = @()
        if ($Command.Count -gt 1) {
            $baseArgs = $Command[1..($Command.Count - 1)]
        }
        $allArgs = @($baseArgs + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"))
        $output = & $Command[0] @allArgs 2>$null
        if ($LASTEXITCODE -ne 0) { return "" }
        return ($output | Out-String).Trim()
    } catch {
        return ""
    }
}

function Get-PythonRunners {
    $runners = @()
    $local312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
    if (Test-Path $local312) { $runners += ,@($local312) }
    $runners += ,@("py", "-3.12")
    $runners += ,@("py", "-3.11")
    $runners += ,@("py", "-3.10")
    $runners += ,@("py", "-3")
    $runners += ,@("python")
    return $runners
}

function Select-CompatiblePythonRunner {
    foreach ($runner in Get-PythonRunners) {
        $ver = Get-PythonVersion -Command $runner
        if (-not $ver) { continue }
        $parts = $ver.Split(".")
        if ($parts.Count -lt 2) { continue }
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -eq 3 -and $minor -ge 10 -and $minor -le 12) {
            return @{
                runner = $runner
                version = $ver
            }
        }
    }
    return $null
}

function Invoke-Checked {
    param(
        [string[]]$Command,
        [string]$ErrorMessage
    )
    if (-not $Command -or $Command.Count -eq 0) {
        throw "Internal error: empty command invocation."
    }
    $args = @()
    if ($Command.Count -gt 1) {
        $args = $Command[1..($Command.Count - 1)]
    }
    & $Command[0] @args
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Get-FceuxExecutable {
    $onPath = Get-Command fceux.exe -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles "FCEUX\fceux.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "FCEUX\fceux.exe"),
        (Join-Path $AppDir "tools\fceux\fceux.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $roots = @()
    if ($env:LocalAppData) {
        $roots += (Join-Path $env:LocalAppData "Microsoft\WinGet\Packages")
        $roots += (Join-Path $env:LocalAppData "Programs")
    }
    $roots += (Join-Path $AppDir "tools\fceux")

    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        try {
            $match = Get-ChildItem -Path $root -Recurse -Filter fceux.exe -File -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($match) { return $match.FullName }
        } catch {
            continue
        }
    }
    return ""
}

function Install-FceuxPortableFallback {
    $toolsDir = Join-Path $AppDir "tools\fceux"
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    $apiUrl = "https://api.github.com/repos/TASEmulators/fceux/releases/latest"
    $headers = @{ "User-Agent" = "LightgunArcadeUpdater" }
    Write-Host "[deps-win] attempting FCEUX portable fallback from GitHub releases"
    $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers
    $asset = $release.assets |
        Where-Object { $_.name -match "(?i)win" -and $_.name -match "(?i)\.zip$" } |
        Select-Object -First 1
    if (-not $asset) {
        throw "Could not find Windows zip asset in latest FCEUX release."
    }
    $zipPath = Join-Path $toolsDir $asset.name
    $extractDir = Join-Path $toolsDir "portable"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -Headers $headers
    if (Test-Path $extractDir) {
        Remove-Item -Recurse -Force $extractDir
    }
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
    return (Get-FceuxExecutable)
}

Write-Host "[deps-win] checking python runtime (requires 3.10 - 3.12)"
$pythonInfo = Select-CompatiblePythonRunner
if (-not $pythonInfo) {
    Write-Host "[deps-win] compatible python not found, attempting install of Python 3.12 via winget"
    $installed = Ensure-WingetPackage -WingetId "Python.Python.3.12"
    if (-not $installed) {
        throw "Python 3.10-3.12 is required. Install Python 3.12 and re-run updater."
    }
    $env:Path += ";$env:LocalAppData\Programs\Python\Python312;$env:LocalAppData\Programs\Python\Python312\Scripts"
    $pythonInfo = Select-CompatiblePythonRunner
    if (-not $pythonInfo) {
        throw "Python 3.12 install attempted but still not available. Open a new terminal and run updater again."
    }
}

$pythonRunner = [string[]]$pythonInfo.runner
$pythonVersion = [string]$pythonInfo.version
Write-Host "[deps-win] using python runner: $($pythonRunner -join ' ') ($pythonVersion)"

Write-Host "[deps-win] checking git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[deps-win] installing Git via winget"
    if (-not (Ensure-WingetPackage -WingetId "Git.Git")) {
        Write-Host "[deps-win] winget not found; install Git manually from https://git-scm.com/download/win"
    }
}

Write-Host "[deps-win] checking fceux"
$fceuxExe = Get-FceuxExecutable
if (-not $fceuxExe) {
    Write-Host "[deps-win] installing FCEUX via winget"
    $installed = Ensure-WingetPackage -WingetId "FCEUX.FCEUX"
    if ($installed) {
        $fceuxExe = Get-FceuxExecutable
    }
    if (-not $fceuxExe) {
        try {
            $fceuxExe = Install-FceuxPortableFallback
        } catch {
            Write-Host "[deps-win] portable fallback failed: $($_.Exception.Message)"
        }
    }
    if (-not $fceuxExe) {
        throw "FCEUX installation failed. Install manually from https://fceux.com/web/download.html"
    }
}
Write-Host "[deps-win] fceux executable: $fceuxExe"

Write-Host "[deps-win] installing python packages"
$pipUpgrade = @($pythonRunner + @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"))
Invoke-Checked -Command $pipUpgrade -ErrorMessage "Failed to upgrade pip/setuptools/wheel."

$pipInstall = @($pythonRunner + @("-m", "pip", "install", "-r", "$AppDir\requirements.txt"))
Invoke-Checked -Command $pipInstall -ErrorMessage "Failed to install Python requirements."

Write-Host "[deps-win] completed"
