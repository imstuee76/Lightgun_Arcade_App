param(
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

function Get-EnvMap {
    param(
        [string]$Path
    )
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line)) { return }
        if ($line.StartsWith("#")) { return }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            $map[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $map
}

function Sync-FromGitHubZip {
    param(
        [string]$AppDir,
        [string]$Repo,
        [string]$Token,
        [string]$PreferredBranch = "main"
    )
    if ([string]::IsNullOrWhiteSpace($Repo)) {
        throw "GITHUB_REPO is not set in .env and no git repo exists."
    }

    $headers = @{
        "User-Agent" = "LightgunArcadeUpdater"
    }
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }

    $branches = @()
    if (-not [string]::IsNullOrWhiteSpace($PreferredBranch)) { $branches += $PreferredBranch }
    $branches += @("main", "master")
    $branches = $branches | Select-Object -Unique

    $tmpZip = $null
    $tmpExtract = $null
    $selectedBranch = $null
    $selectedUrl = $null

    foreach ($branch in $branches) {
        $urlCandidates = @(
            "https://api.github.com/repos/$Repo/zipball/$branch",
            "https://codeload.github.com/$Repo/zip/refs/heads/$branch"
        )
        foreach ($url in $urlCandidates) {
            $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $tmpZip = Join-Path $env:TEMP "lightgun_update_$stamp.zip"
            try {
                Write-Host "[updater-win] trying zip download: $url"
                Invoke-WebRequest -Uri $url -OutFile $tmpZip -Headers $headers
                $selectedBranch = $branch
                $selectedUrl = $url
                break
            } catch {
                if (Test-Path $tmpZip) {
                    Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if ($selectedBranch) { break }
    }

    if (-not $selectedBranch) {
        throw "Could not download repo archive. Verify GITHUB_REPO/GITHUB_BRANCH and token access."
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $tmpExtract = Join-Path $env:TEMP "lightgun_update_$stamp"
    Write-Host "[updater-win] extracting source zip from $selectedUrl"
    Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force

    $sourceRoot = Get-ChildItem -Path $tmpExtract -Directory | Select-Object -First 1
    if (-not $sourceRoot) {
        throw "Downloaded zip did not contain a valid root folder."
    }

    Write-Host "[updater-win] copying updated files (preserving .env and data)"
    Get-ChildItem -Path $sourceRoot.FullName -Recurse -Force | ForEach-Object {
        $relative = $_.FullName.Substring($sourceRoot.FullName.Length).TrimStart("\")
        if ([string]::IsNullOrWhiteSpace($relative)) { return }
        if ($relative -eq ".env") { return }
        if ($relative -like "data\*") { return }
        if ($relative -like ".git\*") { return }
        if ($relative -like "*.sh") { return }

        $destPath = Join-Path $AppDir $relative
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Force -Path $destPath | Out-Null
        } else {
            $destDir = Split-Path -Parent $destPath
            if (-not (Test-Path $destDir)) {
                New-Item -ItemType Directory -Force -Path $destDir | Out-Null
            }
            Copy-Item -Path $_.FullName -Destination $destPath -Force
        }
    }

    Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "[updater-win] zip update completed from branch '$selectedBranch'"
}

$DefaultAppDir = "C:\Lightgun_Arcade_app"
if (Test-Path $DefaultAppDir) {
    $AppDir = $DefaultAppDir
} else {
    $AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$DataDir = Join-Path $AppDir "data"
$UpdaterLogDir = Join-Path $DataDir "logs\updater"
New-Item -ItemType Directory -Force -Path $UpdaterLogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $UpdaterLogDir "updater_$Stamp.log"
Start-Transcript -Path $LogFile -Append | Out-Null

try {
    Write-Host "[updater-win] $(Get-Date -Format s) starting"
    Write-Host "[updater-win] app dir: $AppDir"
    Set-Location $AppDir

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $AppDir "data\logs\app"), `
        (Join-Path $AppDir "data\logs\updater"), `
        (Join-Path $AppDir "data\db"), `
        (Join-Path $AppDir "data\exports"), `
        (Join-Path $AppDir "data\cache") | Out-Null

    $envPath = Join-Path $AppDir ".env"
    $envBackup = $null
    $envVars = @{}
    if (Test-Path $envPath) {
        $envVars = Get-EnvMap -Path $envPath
        $envBackup = [System.IO.Path]::GetTempFileName()
        Copy-Item -Path $envPath -Destination $envBackup -Force
        Write-Host "[updater-win] .env backed up"
    }

    $updated = $false
    if (Test-Path (Join-Path $AppDir ".git")) {
        $preferredBranch = $envVars["GITHUB_BRANCH"]
        if ([string]::IsNullOrWhiteSpace($preferredBranch)) { $preferredBranch = "main" }
        Write-Host "[updater-win] hard resetting to origin/$preferredBranch"
        try {
            git fetch origin $preferredBranch
            if ($LASTEXITCODE -ne 0) { git fetch --all }
            git reset --hard origin/$preferredBranch
            $updated = $true
        } catch {
            Write-Host "[updater-win] git update failed, falling back to zip download"
        }
    } else {
        Write-Host "[updater-win] no git repository found, using zip download mode"
    }

    if (-not $updated) {
        $repo = $envVars["GITHUB_REPO"]
        $token = $envVars["GITHUB_TOKEN"]
        $preferredBranch = $envVars["GITHUB_BRANCH"]
        if ([string]::IsNullOrWhiteSpace($preferredBranch)) { $preferredBranch = "main" }
        Sync-FromGitHubZip -AppDir $AppDir -Repo $repo -Token $token -PreferredBranch $preferredBranch
        $updated = $true
    }

    if ($envBackup -and (Test-Path $envBackup)) {
        Copy-Item -Path $envBackup -Destination $envPath -Force
        Remove-Item -Path $envBackup -Force
        Write-Host "[updater-win] .env restored"
    }

    Write-Host "[updater-win] checking dependencies"
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $AppDir "scripts\install_dependencies_windows.ps1")

    Write-Host "[updater-win] creating desktop shortcuts"
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $AppDir "scripts\create_desktop_shortcuts_windows.ps1")

    Write-Host "[updater-win] checking support files"
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $AppDir "scripts\download_support_files_windows.ps1")

    if (-not $NoLaunch) {
        Write-Host "[updater-win] launching app"
        Start-Process -FilePath (Join-Path $AppDir "run_app_windows.bat") -WorkingDirectory $AppDir
    } else {
        Write-Host "[updater-win] update complete (NoLaunch enabled)"
    }
} finally {
    Stop-Transcript | Out-Null
}
