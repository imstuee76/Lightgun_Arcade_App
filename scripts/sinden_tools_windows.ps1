param(
    [ValidateSet("calibration", "buttons", "diagnostics", "config")]
    [string]$Mode = "config"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
$SindenRoot = Join-Path $AppDir "tools\sinden"

if (-not (Test-Path $SindenRoot)) {
    throw "Sinden tools folder not found: $SindenRoot. Run updater/full install first."
}

$exeCandidates = Get-ChildItem -Path $SindenRoot -Recurse -File -Filter *.exe |
    Where-Object {
        $_.Name -notmatch "unins|uninstall|setup" -and
        ($_.Name -match "Sinden|Lightgun")
    } |
    Sort-Object FullName

if (-not $exeCandidates) {
    throw "No Sinden executable found under $SindenRoot"
}

$target = $exeCandidates | Select-Object -First 1
Write-Host "[sinden-win] mode: $Mode"
Write-Host "[sinden-win] launching: $($target.FullName)"

# Official CLI args are not stable across Sinden releases.
# Launching the Sinden utility UI provides calibration/button/diagnostics tools.
Start-Process -FilePath $target.FullName -WorkingDirectory $target.DirectoryName
