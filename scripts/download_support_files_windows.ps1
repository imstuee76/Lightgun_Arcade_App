param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
$ToolsDir = Join-Path $AppDir "tools\sinden"
New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

$SindenUrl = "https://www.sindenlightgun.com/software/SindenLightgunSoftwareReleaseV2.08b.zip"
$SindenZip = Join-Path $ToolsDir "SindenLightgunSoftwareReleaseV2.08b.zip"
$ExtractDir = Join-Path $ToolsDir "release_v2.08b"

if ((Test-Path $SindenZip) -and -not $Force) {
    Write-Host "[support-win] Sinden package already exists: $SindenZip"
} else {
    Write-Host "[support-win] downloading official Sinden package"
    Invoke-WebRequest -Uri $SindenUrl -OutFile $SindenZip
}

if ((Test-Path $ExtractDir) -and -not $Force) {
    Write-Host "[support-win] extracted folder already exists: $ExtractDir"
} else {
    Write-Host "[support-win] extracting package to $ExtractDir"
    if (Test-Path $ExtractDir) {
        Remove-Item -Recurse -Force $ExtractDir
    }
    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
    Expand-Archive -Path $SindenZip -DestinationPath $ExtractDir -Force
}

Write-Host "[support-win] done"
Write-Host "[support-win] package: $SindenZip"
