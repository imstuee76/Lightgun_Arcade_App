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

function Rank-SindenExecutables {
    param(
        [System.IO.FileInfo[]]$Candidates
    )

    if (-not $Candidates -or $Candidates.Count -eq 0) {
        return @()
    }

    # Rank by likely "real" Sinden UI executable.
    $scored = foreach ($c in $Candidates) {
        $score = 0
        $full = $c.FullName
        $name = $c.Name

        if ($name -match "(?i)^SindenLightgunSoftware.*\.exe$") { $score += 300 }
        if ($name -match "(?i)^Lightgun.*Software.*\.exe$") { $score += 250 }
        if ($name -match "(?i)^Sinden.*Lightgun.*\.exe$") { $score += 220 }
        if ($name -match "(?i)^Lightgun.*\.exe$") { $score += 150 }
        if ($full -match "(?i)\\Windows\\") { $score += 120 }
        if ($full -match "(?i)\\SindenLightgunSoftwareRelease") { $score += 80 }
        if ($full -match "(?i)\\LightgunSoftware") { $score += 50 }
        if ($full -match "(?i)\\Pedal\\") { $score -= 500 }
        if ($full -match "(?i)\\UpdateExistingLinuxBuilds\\") { $score -= 600 }
        if ($full -match "(?i)\\Linux\\") { $score -= 200 }
        if ($full -match "(?i)\\Firmware\\") { $score -= 120 }
        if ($full -match "(?i)\\Driver") { $score -= 120 }
        if ($name -match "(?i)^LightgunMono\.exe$") { $score += 25 }

        [PSCustomObject]@{
            Score    = $score
            FullName = $c.FullName
            Item     = $c
        }
    }

    return @($scored |
        Sort-Object @{ Expression = { $_.Score }; Descending = $true }, @{ Expression = { $_.FullName.Length } }, FullName |
        Select-Object -ExpandProperty Item)
}

$exeCandidates = Get-ChildItem -Path $SindenRoot -Recurse -File -Filter *.exe |
    Where-Object {
        $_.Name -notmatch "(?i)unins|uninstall|setup|installer|driver" -and
        $_.Name -notmatch "(?i)pedal|foot" -and
        $_.FullName -notmatch "(?i)\\Pedal\\" -and
        $_.FullName -notmatch "(?i)\\UpdateExistingLinuxBuilds\\" -and
        $_.FullName -notmatch "(?i)\\Linux\\" -and
        ($_.Name -match "(?i)sinden|lightgun")
    }

if (-not $exeCandidates) {
    throw "No Sinden executable found under $SindenRoot"
}

$targets = Rank-SindenExecutables -Candidates $exeCandidates
if (-not $targets -or $targets.Count -eq 0) {
    throw "Could not select a Sinden executable under $SindenRoot"
}
Write-Host "[sinden-win] mode: $Mode"
Write-Host "[sinden-win] candidate count: $($targets.Count)"

$launchErrors = @()
$launched = $false

# Official CLI args are not stable across Sinden releases.
# Launching the Sinden utility UI provides calibration/button/diagnostics tools.
foreach ($target in $targets | Select-Object -First 6) {
    Write-Host "[sinden-win] launching: $($target.FullName)"
    $proc = Start-Process -FilePath $target.FullName -WorkingDirectory $target.DirectoryName -PassThru
    Start-Sleep -Seconds 2
    $proc.Refresh()
    if (-not $proc.HasExited) {
        $launched = $true
        break
    }

    $launchErrors += "code=$($proc.ExitCode) path=$($target.FullName)"
    Write-Warning "[sinden-win] candidate exited immediately (code $($proc.ExitCode)): $($target.FullName)"
}

if (-not $launched) {
    $details = ($launchErrors -join "; ")
    throw "Sinden utility exited immediately for tested candidates. $details"
}
