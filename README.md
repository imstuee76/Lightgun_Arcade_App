# Lightgun Arcade App

Standalone desktop launcher for Linux and Windows, built for:

- Sinden Lightgun setup helpers
- Xbox controller navigation
- ROM library browser with matching artwork previews
- FCEUX game launching (no MAME)
- High score tracking (SQLite + Excel export)
- Git-based updater and auto-sync versioning

## Install Paths

Linux target:

`/home/arcade/Lightgun_Arcade_app/`

Windows target:

`C:\Lightgun_Arcade_app\`

Persistent runtime files are stored in:

Linux: `/home/arcade/Lightgun_Arcade_app/data/`  
Windows: `C:\Lightgun_Arcade_app\data\`

## Quick Start (Linux)

```bash
cd /home/arcade/Lightgun_Arcade_app/
chmod +x update_lightgun_app.sh run_app.sh scripts/*.sh
./update_lightgun_app.sh
```

The updater will:

1. hard-reset to latest `main`
2. preserve `.env` and `data/`
3. install missing dependencies
4. create desktop shortcuts
5. launch the app

## Quick Start (Windows)

Option A (minimal bootstrap):

1. Create folder: `C:\Lightgun_Arcade_app\`
2. Copy only:
   - `bootstrap_windows.bat`
   - `bootstrap_windows.ps1`
   - `.env`
3. Double-click:
`C:\Lightgun_Arcade_app\bootstrap_windows.bat`

This downloads latest Windows-needed files from GitHub, then runs full install.
Bootstrap writes a root log file like:
`C:\Lightgun_Arcade_app\bootstrap_windows_YYYYMMDD_HHMMSS.log`

Option B (full folder already copied):

1. Copy this full folder to `C:\Lightgun_Arcade_app\`
2. Put your `.env` in `C:\Lightgun_Arcade_app\.env`
3. Double-click:
`C:\Lightgun_Arcade_app\start_windows.bat`

For full first-time install (deps + support files + launch), use:
`C:\Lightgun_Arcade_app\full_install_windows.bat`

Windows first-run does:

1. hard-reset to latest `main`
2. preserve `.env` and `data\`
3. install missing dependencies (Python packages, Git/FCEUX via winget if available)
4. create desktop launcher `.bat` files
5. launch the app

To update only (no app launch), run:
`C:\Lightgun_Arcade_app\update_only_windows.bat`

After install:
1. Put ROMs in `C:\Lightgun_Arcade_app\roms\`
2. Open app and click `Turnkey Setup` in `App Settings`
3. Set your `Player Name` in `App Settings`
4. Launch game from `Game Library`

Notes:
- If `.git` exists, updater uses `git fetch/reset`.
- If `.git` is missing, updater downloads latest `main` zip from `GITHUB_REPO` in `.env`.
- In both modes, `.env` and `data\` are preserved.
- Updater now also checks/downloads Windows support files (Sinden package).
- Zip update mode skips Linux `.sh` files on Windows.

If you want to run bootstrap from PowerShell with live output:
```powershell
cd C:\Lightgun_Arcade_app\
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap_windows.ps1
```

## Supporting Files You Need

### 1) ROMs (required, manual)
- Source: your own legal game dumps.
- Put in:
  - Linux: `/home/arcade/Lightgun_Arcade_app/roms/`
  - Windows: `C:\Lightgun_Arcade_app\roms\`
- Example: `duck_hunt.nes`

### 2) Artwork images (optional but recommended)
- Put in same folder as ROMs, or a separate folder configured in UI.
- Must match ROM basename.
- Example: `duck_hunt.png` for `duck_hunt.nes`

### 3) Sinden software package (optional helper download)
- Official source: `https://www.sindenlightgun.com/software/SindenLightgunSoftwareReleaseV2.08b.zip`
- Auto-download command (Linux):
```bash
cd /home/arcade/Lightgun_Arcade_app/
bash scripts/download_support_files.sh
```
- Auto-download command (Windows PowerShell):
```powershell
cd C:\Lightgun_Arcade_app\
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\download_support_files_windows.ps1
```
- Download location:
  - Linux: `/home/arcade/Lightgun_Arcade_app/tools/sinden/`
  - Windows: `C:\Lightgun_Arcade_app\tools\sinden\`
- Windows app auto-fills Sinden commands and launches Sinden utility UI from this folder.

### 4) Git credentials (.env) (required for auto-sync)
- Path:
  - Linux: `/home/arcade/Lightgun_Arcade_app/.env`
  - Windows: `C:\Lightgun_Arcade_app\.env`
- Keys:
  - `GITHUB_TOKEN=...`
  - `GITHUB_REPO=owner/repo`
  - Optional: `GITHUB_BRANCH=main` (or your actual branch)

## Runtime Logs

- App logs: `data/logs/app/`
- Updater logs: `data/logs/updater/`
- App error logs: `data/logs/app/errors_YYYYMMDD.log`

Each run creates a timestamped log file.

## ROM + Artwork Rules

- Put ROM files in your configured ROM folder.
- Put artwork with the same base name as ROM:
  - `duck_hunt.nes`
  - `duck_hunt.png` (or `.jpg`, `.jpeg`, `.bmp`, `.gif`)

## Auto Git Sync

When settings or high scores are saved from the app, it triggers:

- Linux: `scripts/git_autosync.sh`
- Windows: `scripts/git_autosync_windows.ps1`

- bumps build number in `VERSION` (`0.1.0+N`)
- commits all changes
- pushes to `main` using `.env` credentials

`.env` expected keys:

- `GITHUB_TOKEN=...`
- `GITHUB_REPO=owner/repo`

Optional:

- `GIT_USER_NAME=...`
- `GIT_USER_EMAIL=...`

## Auto Score Capture

- Duck Hunt scores are captured continuously from emulator memory during play.
- Each completed run score is appended to the app database without closing/reopening app.
- Player name comes from `App Settings -> Player Name`.
- Error details are written to `data/logs/app/errors_YYYYMMDD.log`.
