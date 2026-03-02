from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from .paths import ACTIVE_ROOT, AUTO_SYNC_SCRIPT


def trigger_auto_sync(reason: str, branch: str, logger: logging.Logger) -> None:
    if not AUTO_SYNC_SCRIPT.exists():
        logger.warning("Auto sync script missing: %s", AUTO_SYNC_SCRIPT)
        return

    def _run() -> None:
        try:
            if os.name == "nt":
                command = [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(AUTO_SYNC_SCRIPT),
                    "-Branch",
                    branch,
                    "-Reason",
                    reason,
                ]
            else:
                command = ["bash", str(AUTO_SYNC_SCRIPT), branch, reason]

            subprocess.run(
                command,
                cwd=ACTIVE_ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Auto sync completed for reason: %s", reason)
        except Exception as exc:  # pragma: no cover - safety path
            logger.warning("Auto sync failed: %s", exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def read_env_value(key: str) -> str:
    env_file = Path(ACTIVE_ROOT) / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, value = stripped.split("=", 1)
        if k.strip() == key:
            return value.strip()
    return ""
