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

function Select-SindenExecutable {
    param(
        [System.IO.FileInfo[]]$Candidates
    )

    if (-not $Candidates -or $Candidates.Count -eq 0) {
        return $null
    }

    # Prefer the actual lightgun software executable and avoid pedal-only utilities.
    $prioritizedPatterns = @(
        "(?i)^SindenLightgunSoftware.*\.exe$",
        "(?i)^Lightgun.*Software.*\.exe$",
        "(?i)^Sinden.*Lightgun.*\.exe$",
        "(?i)^Lightgun.*\.exe$"
    )

    foreach ($pattern in $prioritizedPatterns) {
        $match = $Candidates | Where-Object { $_.Name -match $pattern } | Select-Object -First 1
        if ($match) {
            return $match
        }
    }

    # Fallback: first candidate sorted by shortest path (usually top-level app exe).
    return $Candidates | Sort-Object @{ Expression = { $_.FullName.Length } }, FullName | Select-Object -First 1
}

$exeCandidates = Get-ChildItem -Path $SindenRoot -Recurse -File -Filter *.exe |
    Where-Object {
        $_.Name -notmatch "(?i)unins|uninstall|setup|installer|driver" -and
        $_.Name -notmatch "(?i)pedal|foot" -and
        ($_.Name -match "(?i)sinden|lightgun")
    }

if (-not $exeCandidates) {
    throw "No Sinden executable found under $SindenRoot"
}

$target = Select-SindenExecutable -Candidates $exeCandidates
if (-not $target) {
    throw "Could not select a Sinden executable under $SindenRoot"
}
Write-Host "[sinden-win] mode: $Mode"
Write-Host "[sinden-win] launching: $($target.FullName)"

# Official CLI args are not stable across Sinden releases.
# Launching the Sinden utility UI provides calibration/button/diagnostics tools.
$proc = Start-Process -FilePath $target.FullName -WorkingDirectory $target.DirectoryName -PassThru
Start-Sleep -Seconds 2
$proc.Refresh()
if ($proc.HasExited) {
    throw "Sinden utility exited immediately (code $($proc.ExitCode)). Path: $($target.FullName)"
}
