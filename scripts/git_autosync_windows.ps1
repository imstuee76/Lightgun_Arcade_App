param(
    [string]$Branch = "main",
    [string]$Reason = "app-change"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $AppDir ".env"
$VersionFile = Join-Path $AppDir "VERSION"

if (-not (Test-Path $EnvFile)) { exit 0 }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 0 }

try {
    git -C $AppDir rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) { exit 0 }
} catch {
    exit 0
}

$envVars = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ([string]::IsNullOrWhiteSpace($line)) { return }
    if ($line.StartsWith("#")) { return }
    $parts = $line.Split("=", 2)
    if ($parts.Count -eq 2) {
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$token = $envVars["GITHUB_TOKEN"]
$repo = $envVars["GITHUB_REPO"]
if ([string]::IsNullOrWhiteSpace($token) -or [string]::IsNullOrWhiteSpace($repo)) { exit 0 }

Set-Location $AppDir
$pending = git status --porcelain
if ([string]::IsNullOrWhiteSpace(($pending | Out-String).Trim())) { exit 0 }

$version = "0.1.0+0"
if (Test-Path $VersionFile) {
    $version = (Get-Content $VersionFile -Raw).Trim()
}

$base = "0.1.0"
$build = 0
if ($version -match "^(.+)\+(\d+)$") {
    $base = $Matches[1]
    $build = [int]$Matches[2]
} elseif (-not [string]::IsNullOrWhiteSpace($version)) {
    $base = $version
}
$nextVersion = "$base+$($build + 1)"
Set-Content -Path $VersionFile -Value $nextVersion -Encoding ASCII

git add -A
$pendingAfter = git status --porcelain
if ([string]::IsNullOrWhiteSpace(($pendingAfter | Out-String).Trim())) { exit 0 }

$userName = $envVars["GIT_USER_NAME"]
$userEmail = $envVars["GIT_USER_EMAIL"]
if ([string]::IsNullOrWhiteSpace($userName)) { $userName = "Lightgun Auto Sync" }
if ([string]::IsNullOrWhiteSpace($userEmail)) { $userEmail = "lightgun@local" }

git config user.name $userName
git config user.email $userEmail
git commit -m "auto: $Reason | v$nextVersion | $(Get-Date -Format s)" *> $null

$remoteUrl = "https://$token@github.com/$repo.git"
git remote get-url origin *> $null
if ($LASTEXITCODE -eq 0) {
    git remote set-url origin $remoteUrl
} else {
    git remote add origin $remoteUrl
}

git push origin $Branch *> $null
