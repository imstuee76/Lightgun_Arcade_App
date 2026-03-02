from __future__ import annotations

import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
if os.name == "nt":
    DEFAULT_INSTALL_ROOT = Path("C:/Lightgun_Arcade_app")
else:
    DEFAULT_INSTALL_ROOT = Path("/home/arcade/Lightgun_Arcade_app")

INSTALL_ROOT = Path(os.getenv("LIGHTGUN_INSTALL_DIR", str(DEFAULT_INSTALL_ROOT)))

if INSTALL_ROOT.exists():
    ACTIVE_ROOT = INSTALL_ROOT
else:
    ACTIVE_ROOT = APP_ROOT

DATA_DIR = Path(os.getenv("LIGHTGUN_DATA_DIR", str(ACTIVE_ROOT / "data")))
LOG_APP_DIR = DATA_DIR / "logs" / "app"
LOG_UPDATER_DIR = DATA_DIR / "logs" / "updater"
DB_DIR = DATA_DIR / "db"
EXPORT_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"
SETTINGS_FILE = DATA_DIR / "settings.json"
HIGHSCORE_DB = DB_DIR / "high_scores.sqlite3"
HIGHSCORE_XLSX = EXPORT_DIR / "high_scores.xlsx"
VERSION_FILE = ACTIVE_ROOT / "VERSION"
if os.name == "nt":
    UPDATE_SCRIPT = ACTIVE_ROOT / "update_lightgun_app_windows.ps1"
    RUN_SCRIPT = ACTIVE_ROOT / "run_app_windows.bat"
    AUTO_SYNC_SCRIPT = ACTIVE_ROOT / "scripts" / "git_autosync_windows.ps1"
else:
    UPDATE_SCRIPT = ACTIVE_ROOT / "update_lightgun_app.sh"
    RUN_SCRIPT = ACTIVE_ROOT / "run_app.sh"
    AUTO_SYNC_SCRIPT = ACTIVE_ROOT / "scripts" / "git_autosync.sh"


def ensure_runtime_dirs() -> None:
    for directory in [DATA_DIR, LOG_APP_DIR, LOG_UPDATER_DIR, DB_DIR, EXPORT_DIR, CACHE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
