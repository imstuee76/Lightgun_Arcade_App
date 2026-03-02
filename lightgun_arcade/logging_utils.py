from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .paths import LOG_APP_DIR


def create_app_logger() -> logging.Logger:
    LOG_APP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_APP_DIR / f"app_{timestamp}.log"

    logger = logging.getLogger("lightgun_arcade")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("App logger initialized: %s", log_path)
    return logger

