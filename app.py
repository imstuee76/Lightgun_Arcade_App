from __future__ import annotations

import tkinter as tk

from lightgun_arcade.logging_utils import create_app_logger
from lightgun_arcade.main_window import LightgunArcadeApp
from lightgun_arcade.paths import ensure_runtime_dirs


def main() -> None:
    ensure_runtime_dirs()
    logger = create_app_logger()
    logger.info("Starting Lightgun Arcade App")

    root = tk.Tk()
    LightgunArcadeApp(root, logger)
    root.mainloop()


if __name__ == "__main__":
    main()

