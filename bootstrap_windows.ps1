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

function Get-BranchCandidates {
    param(
        [string]$Preferred
    )
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Preferred)) { $candidates += $Preferred }
    $candidates += @("main", "master")
    return $candidates | Select-Object -Unique
}

function Get-RepoDefaultBranch {
    param(
        [string]$Repo,
        [string]$Token
    )
    $headers = @{ "User-Agent" = "LightgunBootstrap" }
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }
    try {
        $metaUrl = "https://api.github.com/repos/$Repo"
        $resp = Invoke-WebRequest -Uri $metaUrl -Headers $headers
        $obj = $resp.Content | ConvertFrom-Json
        return [string]$obj.default_branch
    } catch {
        return ""
    }
}

function Download-RepoZip {
    param(
        [string]$Repo,
        [string]$Token,
        [string]$PreferredBranch,
        [string]$Prefix
    )

    $headers = @{ "User-Agent" = "LightgunBootstrap" }
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }

    # First try GitHub zipball with no explicit ref (default branch).
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $defaultZip = Join-Path $env:TEMP "$Prefix`_$stamp.zip"
    try {
        $defaultUrl = "https://api.github.com/repos/$Repo/zipball"
        Write-Host "[bootstrap-win] trying default zipball: $defaultUrl"
        Invoke-WebRequest -Uri $defaultUrl -OutFile $defaultZip -Headers $headers
        Write-Host "[bootstrap-win] download success using default zipball"
        return @{
            ZipPath = $defaultZip
            Branch = ""
            Url = $defaultUrl
        }
    } catch {
        if (Test-Path $defaultZip) {
            Remove-Item -Path $defaultZip -Force -ErrorAction SilentlyContinue
        }
    }

    $detectedDefault = Get-RepoDefaultBranch -Repo $Repo -Token $Token
    $branches = @()
    if (-not [string]::IsNullOrWhiteSpace($PreferredBranch)) { $branches += $PreferredBranch }
    if (-not [string]::IsNullOrWhiteSpace($detectedDefault)) { $branches += $detectedDefault }
    $branches += @("main", "Main", "master", "Master")
    $branches = $branches | Select-Object -Unique

    foreach ($branch in $Branches) {
        $urlCandidates = @(
            "https://api.github.com/repos/$Repo/zipball/$branch",
            "https://codeload.github.com/$Repo/zip/refs/heads/$branch"
        )
        foreach ($url in $urlCandidates) {
            $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $tmpZip = Join-Path $env:TEMP "$Prefix`_$stamp.zip"
            try {
                Write-Host "[bootstrap-win] trying $url"
                Invoke-WebRequest -Uri $url -OutFile $tmpZip -Headers $headers
                Write-Host "[bootstrap-win] download success for branch '$branch'"
                return @{
                    ZipPath = $tmpZip
                    Branch = $branch
                    Url = $url
                }
            } catch {
                Write-Host "[bootstrap-win] download failed for $url"
                if (Test-Path $tmpZip) {
                    Remove-Item -Path $tmpZip -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }

    throw "Failed to download repo archive. Check GITHUB_REPO, branch name case, and token access."
}

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $AppDir "bootstrap_windows_$Stamp.log"
Start-Transcript -Path $LogFile -Append | Out-Null

try {
    Write-Host "[bootstrap-win] app dir: $AppDir"
    Write-Host "[bootstrap-win] log file: $LogFile"

    $envPath = Join-Path $AppDir ".env"
    if (-not (Test-Path $envPath)) {
        throw "Missing .env in $AppDir"
    }

    $envVars = Get-EnvMap -Path $envPath
    $repo = $envVars["GITHUB_REPO"]
    $token = $envVars["GITHUB_TOKEN"]
    $branch = $envVars["GITHUB_BRANCH"]
    if ([string]::IsNullOrWhiteSpace($repo)) {
        throw "GITHUB_REPO missing in .env (expected owner/repo)"
    }

    Write-Host "[bootstrap-win] repo: $repo"
    if (-not [string]::IsNullOrWhiteSpace($branch)) {
        Write-Host "[bootstrap-win] preferred branch from .env: $branch"
    }

    $download = Download-RepoZip -Repo $repo -Token $token -PreferredBranch $branch -Prefix "lightgun_bootstrap"

    $tmpExtract = Join-Path $env:TEMP "lightgun_bootstrap_$Stamp"
    Write-Host "[bootstrap-win] extracting app zip from $($download.Url)"
    Expand-Archive -Path $download.ZipPath -DestinationPath $tmpExtract -Force

    $sourceRoot = Get-ChildItem -Path $tmpExtract -Directory | Select-Object -First 1
    if (-not $sourceRoot) {
        throw "Downloaded zip does not contain a valid root folder."
    }

    Write-Host "[bootstrap-win] copying files (preserving .env and data)"
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

    Remove-Item -Path $download.ZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue

    $fullInstall = Join-Path $AppDir "full_install_windows.bat"
    if (-not (Test-Path $fullInstall)) {
        throw "full_install_windows.bat not found after download."
    }

    Write-Host "[bootstrap-win] starting full install"
    $proc = Start-Process -FilePath $fullInstall -WorkingDirectory $AppDir -PassThru -Wait
    if ($proc.ExitCode -ne 0) {
        throw "full_install_windows.bat failed with exit code $($proc.ExitCode)"
    }

    Write-Host "[bootstrap-win] completed successfully"
} catch {
    Write-Host "[bootstrap-win] ERROR: $($_.Exception.Message)"
    Write-Host "[bootstrap-win] verify .env: GITHUB_REPO=owner/repo and optional GITHUB_BRANCH"
    Write-Host "[bootstrap-win] confirm repo exists at: https://github.com/<owner>/<repo>"
    throw
} finally {
    Stop-Transcript | Out-Null
}
