from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import ACTIVE_ROOT, DATA_DIR, SETTINGS_FILE

if os.name == "nt":
    default_emulator_command = 'fceux.exe --fullscreen 1 "{rom}"'
else:
    default_emulator_command = 'fceux --fullscreen "{rom}"'


DEFAULT_SETTINGS: dict[str, Any] = {
    "library": {
        "rom_dir": str(ACTIVE_ROOT / "roms"),
        "image_dir": str(ACTIVE_ROOT / "roms"),
        "rom_extensions": [".nes", ".zip", ".fds", ".unf", ".unif"],
        "show_scheduled_only": False,
        "sort_mode": "Install Date (Newest)",
    },
    "game_schedules": {},
    "sinden": {
        "calibration_command": "",
        "button_config_command": "",
        "diagnostics_command": "",
        "screen_width": 1920,
        "screen_height": 1080,
        "links": {
            "Sinden Details": "https://sindenlightgun.com/details/",
            "Sinden Support": "https://www.sindenwiki.org/wiki/Sinden_Wiki",
            "Sinden Downloads": "https://www.sindenwiki.org/wiki/Downloads",
        },
    },
    "controller": {
        "deadzone": 0.45,
        "repeat_ms": 200,
        "button_map": {
            "select": 0,
            "back": 1,
            "tab_next": 5,
            "tab_prev": 4,
        },
        "resolution": "",
    },
    "app": {
        "emulator_command": default_emulator_command,
        "git_branch": "main",
        "auto_git_sync": True,
        "auto_score_capture": True,
        "player_name": os.getenv("USERNAME", "Player"),
        "resource_links": {
            "FCEUX Docs": "https://fceux.com/web/help/fceux.html",
            "Sinden Details": "https://sindenlightgun.com/details/",
            "Sinden Wiki": "https://www.sindenwiki.org/wiki/Sinden_Wiki",
            "Linux Mint Docs": "https://linuxmint-user-guide.readthedocs.io/en/latest/",
        },
    },
}


def _deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(default)
    for key, value in loaded.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self.path = path
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return deepcopy(DEFAULT_SETTINGS)
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return deepcopy(DEFAULT_SETTINGS)
            return _deep_merge(DEFAULT_SETTINGS, loaded)
        except Exception:
            return deepcopy(DEFAULT_SETTINGS)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, indent=2, ensure_ascii=True)
        self.path.write_text(payload, encoding="utf-8")
