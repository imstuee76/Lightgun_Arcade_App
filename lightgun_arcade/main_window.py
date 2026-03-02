from __future__ import annotations

import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
import traceback
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .controller_input import ControllerInput
from .git_sync import read_env_value, trigger_auto_sync
from .high_scores import HighScoreStore
from .paths import (
    ACTIVE_ROOT,
    DATA_DIR,
    HIGHSCORE_XLSX,
    LOG_APP_DIR,
    RUN_SCRIPT,
    UPDATE_SCRIPT,
    VERSION_FILE,
    ensure_runtime_dirs,
)
from .settings import SettingsStore

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional runtime dependency
    Image = None
    ImageTk = None


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class LightgunArcadeApp:
    def __init__(self, root: tk.Tk, logger: Any) -> None:
        self.root = root
        self.logger = logger
        ensure_runtime_dirs()

        self.settings_store = SettingsStore()
        self.settings = self.settings_store.data
        self._apply_turnkey_defaults()
        self.high_scores = HighScoreStore()
        self.action_queue: "queue.Queue[str]" = queue.Queue()
        self.controller = ControllerInput(self.action_queue, self.settings["controller"], self.logger)
        self.controller.start()

        self.games: list[dict[str, Any]] = []
        self.preview_image: Any = None

        self.status_var = tk.StringVar(value="Ready")

        self._init_window()
        self._build_ui()
        self._load_games()
        self._refresh_high_scores()

        self.root.after(80, self._poll_controller_actions)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_window(self) -> None:
        version = self._read_version()
        self.root.title(f"Lightgun Arcade App v{version}")
        self.root.geometry("1300x800")
        self.root.minsize(1150, 700)

    def _read_version(self) -> str:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.1.0+0"
        return "0.1.0+0"

    def _apply_turnkey_defaults(self) -> None:
        changed = False
        library = self.settings.get("library", {})
        app_settings = self.settings.get("app", {})
        sinden = self.settings.get("sinden", {})

        default_rom_dir = str(ACTIVE_ROOT / "roms")
        if not library.get("rom_dir"):
            library["rom_dir"] = default_rom_dir
            changed = True
        if not library.get("image_dir"):
            library["image_dir"] = default_rom_dir
            changed = True

        detected_fceux = self._find_fceux_executable()
        current_emulator = str(app_settings.get("emulator_command", "")).strip()
        if detected_fceux and (not current_emulator or "fceux" in current_emulator.lower()):
            app_settings["emulator_command"] = self._default_emulator_command(detected_fceux)
            changed = True
        elif not current_emulator:
            app_settings["emulator_command"] = self._default_emulator_command(detected_fceux)
            changed = True

        if os.name == "nt":
            script_path = ACTIVE_ROOT / "scripts" / "sinden_tools_windows.ps1"
            if script_path.exists():
                calibration_cmd = (
                    f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script_path}" -Mode calibration'
                )
                button_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script_path}" -Mode buttons'
                diagnostics_cmd = (
                    f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script_path}" -Mode diagnostics'
                )
                if not str(sinden.get("calibration_command", "")).strip():
                    sinden["calibration_command"] = calibration_cmd
                    changed = True
                if not str(sinden.get("button_config_command", "")).strip():
                    sinden["button_config_command"] = button_cmd
                    changed = True
                if not str(sinden.get("diagnostics_command", "")).strip():
                    sinden["diagnostics_command"] = diagnostics_cmd
                    changed = True

        if changed:
            self.settings_store.save()
            self.logger.info("Turnkey defaults applied to settings")

    @staticmethod
    def _default_emulator_command(exe_path: str | None = None) -> str:
        if os.name == "nt":
            if exe_path:
                return f'"{exe_path}" --fullscreen 1 "{{rom}}"'
            return 'fceux.exe --fullscreen 1 "{rom}"'
        if exe_path:
            return f'"{exe_path}" --fullscreen "{{rom}}"'
        return 'fceux --fullscreen "{rom}"'

    def _find_fceux_executable(self) -> str | None:
        candidates: list[str] = []
        found = shutil.which("fceux.exe" if os.name == "nt" else "fceux")
        if found:
            return found
        if os.name == "nt":
            try:
                where_output = subprocess.run(
                    ["where", "fceux.exe"], check=False, capture_output=True, text=True
                ).stdout.strip()
                for line in where_output.splitlines():
                    candidate = line.strip()
                    if candidate and Path(candidate).exists():
                        return candidate
            except Exception:
                pass

            pf = os.environ.get("ProgramFiles", r"C:\Program Files")
            pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            local = os.environ.get("LOCALAPPDATA", "")
            candidates.extend(
                [
                    str(Path(pf) / "FCEUX" / "fceux.exe"),
                    str(Path(pfx86) / "FCEUX" / "fceux.exe"),
                    str(ACTIVE_ROOT / "tools" / "fceux" / "fceux.exe"),
                ]
            )
            if local:
                winget_root = Path(local) / "Microsoft" / "WinGet" / "Packages"
                if winget_root.exists():
                    try:
                        for candidate in winget_root.rglob("fceux.exe"):
                            candidates.append(str(candidate))
                    except Exception:
                        pass
                programs_root = Path(local) / "Programs"
                if programs_root.exists():
                    try:
                        for candidate in programs_root.rglob("fceux.exe"):
                            candidates.append(str(candidate))
                    except Exception:
                        pass

            tools_root = ACTIVE_ROOT / "tools" / "fceux"
            if tools_root.exists():
                try:
                    for candidate in tools_root.rglob("fceux.exe"):
                        candidates.append(str(candidate))
                except Exception:
                    pass
        else:
            candidates.extend(
                [
                    str(Path("/usr/bin/fceux")),
                    str(Path("/usr/local/bin/fceux")),
                    str(ACTIVE_ROOT / "tools" / "fceux" / "fceux"),
                ]
            )
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return None

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.library_tab = ttk.Frame(self.notebook)
        self.sinden_tab = ttk.Frame(self.notebook)
        self.controller_tab = ttk.Frame(self.notebook)
        self.app_tab = ttk.Frame(self.notebook)
        self.scores_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.library_tab, text="Game Library")
        self.notebook.add(self.sinden_tab, text="Sinden Config")
        self.notebook.add(self.controller_tab, text="Controller")
        self.notebook.add(self.app_tab, text="App Settings")
        self.notebook.add(self.scores_tab, text="High Scores")

        self._build_library_tab()
        self._build_sinden_tab()
        self._build_controller_tab()
        self._build_app_tab()
        self._build_scores_tab()

        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=10, pady=(0, 6))

    def _build_tab_header(self, tab: ttk.Frame) -> ttk.Frame:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="Save Settings", command=self.save_all_settings).pack(side="left")
        return bar

    def _build_library_tab(self) -> None:
        self._build_tab_header(self.library_tab)

        library = self.settings["library"]
        self.rom_dir_var = tk.StringVar(value=library.get("rom_dir", ""))
        self.image_dir_var = tk.StringVar(value=library.get("image_dir", ""))
        self.show_scheduled_only_var = tk.BooleanVar(value=bool(library.get("show_scheduled_only", False)))
        self.sort_mode_var = tk.StringVar(value=library.get("sort_mode", "Install Date (Newest)"))

        controls = ttk.Frame(self.library_tab)
        controls.pack(fill="x", padx=8)

        ttk.Label(controls, text="ROM Folder").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=4)
        ttk.Entry(controls, textvariable=self.rom_dir_var, width=80).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(controls, text="Browse", command=lambda: self._pick_folder(self.rom_dir_var)).grid(
            row=0, column=2, padx=4
        )

        ttk.Label(controls, text="Image Folder").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=4)
        ttk.Entry(controls, textvariable=self.image_dir_var, width=80).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(controls, text="Browse", command=lambda: self._pick_folder(self.image_dir_var)).grid(
            row=1, column=2, padx=4
        )

        ttk.Checkbutton(
            controls, text="Show Scheduled Only", variable=self.show_scheduled_only_var, command=self._load_games
        ).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Label(controls, text="Sort").grid(row=2, column=1, sticky="e", padx=(0, 4))

        self.sort_combo = ttk.Combobox(
            controls,
            textvariable=self.sort_mode_var,
            values=["Name (A-Z)", "Install Date (Newest)", "Install Date (Oldest)"],
            state="readonly",
            width=26,
        )
        self.sort_combo.grid(row=2, column=2, sticky="w", pady=4)
        self.sort_combo.bind("<<ComboboxSelected>>", lambda _: self._load_games())
        ttk.Button(controls, text="Refresh", command=self._load_games).grid(row=2, column=3, padx=4)
        controls.columnconfigure(1, weight=1)

        split = ttk.Panedwindow(self.library_tab, orient="horizontal")
        split.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(split)
        right = ttk.Frame(split)
        split.add(left, weight=4)
        split.add(right, weight=5)

        self.game_list = tk.Listbox(left, height=25, font=("TkDefaultFont", 11))
        self.game_list.pack(side="left", fill="both", expand=True)
        self.game_list.bind("<<ListboxSelect>>", self._on_game_selected)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.game_list.yview)
        scroll.pack(side="right", fill="y")
        self.game_list.config(yscrollcommand=scroll.set)

        launch_bar = ttk.Frame(self.library_tab)
        launch_bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(launch_bar, text="Launch Selected Game", command=self.launch_selected_game).pack(side="left")

        self.preview_label = ttk.Label(right, text="No artwork selected", anchor="center")
        self.preview_label.pack(fill="both", expand=True, pady=(0, 8))

        schedule = ttk.LabelFrame(right, text="Game Schedule")
        schedule.pack(fill="x", pady=4)
        self.schedule_enabled_var = tk.BooleanVar(value=False)
        self.schedule_start_var = tk.StringVar(value="08:00")
        self.schedule_end_var = tk.StringVar(value="23:00")
        self.day_vars = [tk.BooleanVar(value=True) for _ in range(7)]

        ttk.Checkbutton(schedule, text="Enable Schedule", variable=self.schedule_enabled_var).grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Label(schedule, text="Start (HH:MM)").grid(row=0, column=1, padx=6, pady=4)
        ttk.Entry(schedule, textvariable=self.schedule_start_var, width=8).grid(row=0, column=2, padx=6, pady=4)
        ttk.Label(schedule, text="End (HH:MM)").grid(row=0, column=3, padx=6, pady=4)
        ttk.Entry(schedule, textvariable=self.schedule_end_var, width=8).grid(row=0, column=4, padx=6, pady=4)

        for idx, day_name in enumerate(DAY_NAMES):
            ttk.Checkbutton(schedule, text=day_name, variable=self.day_vars[idx]).grid(
                row=1, column=idx, padx=4, pady=4, sticky="w"
            )
        ttk.Button(schedule, text="Apply To Selected Game", command=self._apply_schedule_to_selected).grid(
            row=2, column=0, padx=6, pady=8, sticky="w"
        )

    def _build_sinden_tab(self) -> None:
        self._build_tab_header(self.sinden_tab)
        sinden = self.settings["sinden"]
        self.calibration_cmd_var = tk.StringVar(value=sinden.get("calibration_command", ""))
        self.button_cfg_cmd_var = tk.StringVar(value=sinden.get("button_config_command", ""))
        self.diagnostics_cmd_var = tk.StringVar(value=sinden.get("diagnostics_command", ""))
        self.screen_width_var = tk.IntVar(value=int(sinden.get("screen_width", 1920)))
        self.screen_height_var = tk.IntVar(value=int(sinden.get("screen_height", 1080)))

        frame = ttk.Frame(self.sinden_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        ttk.Label(frame, text="Calibration Command").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.calibration_cmd_var, width=90).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(frame, text="Run", command=lambda: self._run_shell(self.calibration_cmd_var.get())).grid(
            row=0, column=2, padx=8
        )

        ttk.Label(frame, text="Button Config Command").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.button_cfg_cmd_var, width=90).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(frame, text="Run", command=lambda: self._run_shell(self.button_cfg_cmd_var.get())).grid(
            row=1, column=2, padx=8
        )

        ttk.Label(frame, text="Diagnostics Command").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.diagnostics_cmd_var, width=90).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(frame, text="Run", command=lambda: self._run_shell(self.diagnostics_cmd_var.get())).grid(
            row=2, column=2, padx=8
        )

        screen_box = ttk.LabelFrame(frame, text="Screen Settings")
        screen_box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Label(screen_box, text="Width").grid(row=0, column=0, padx=6, pady=6)
        ttk.Entry(screen_box, textvariable=self.screen_width_var, width=8).grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(screen_box, text="Height").grid(row=0, column=2, padx=6, pady=6)
        ttk.Entry(screen_box, textvariable=self.screen_height_var, width=8).grid(row=0, column=3, padx=6, pady=6)

        links_box = ttk.LabelFrame(frame, text="Sinden Links")
        links_box.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        links = sinden.get("links", {})
        col = 0
        for title, link in links.items():
            ttk.Button(links_box, text=title, command=lambda href=link: webbrowser.open(href)).grid(
                row=0, column=col, padx=6, pady=6
            )
            col += 1
        ttk.Button(
            frame,
            text="Open Sinden Utility",
            command=lambda: self._run_shell(self.calibration_cmd_var.get()),
        ).grid(row=5, column=0, sticky="w", pady=6)
        frame.columnconfigure(1, weight=1)

    def _build_controller_tab(self) -> None:
        self._build_tab_header(self.controller_tab)
        controller = self.settings["controller"]
        button_map = controller.get("button_map", {})
        self.deadzone_var = tk.DoubleVar(value=float(controller.get("deadzone", 0.45)))
        self.repeat_ms_var = tk.IntVar(value=int(controller.get("repeat_ms", 200)))
        self.btn_select_var = tk.IntVar(value=int(button_map.get("select", 0)))
        self.btn_back_var = tk.IntVar(value=int(button_map.get("back", 1)))
        self.btn_tab_next_var = tk.IntVar(value=int(button_map.get("tab_next", 5)))
        self.btn_tab_prev_var = tk.IntVar(value=int(button_map.get("tab_prev", 4)))
        self.resolution_var = tk.StringVar(value=controller.get("resolution", ""))

        frame = ttk.Frame(self.controller_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        input_map = ttk.LabelFrame(frame, text="Xbox Button Mapping")
        input_map.pack(fill="x", pady=6)
        ttk.Label(input_map, text="Select (A)").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Entry(input_map, textvariable=self.btn_select_var, width=6).grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(input_map, text="Back (B)").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ttk.Entry(input_map, textvariable=self.btn_back_var, width=6).grid(row=0, column=3, padx=6, pady=6)
        ttk.Label(input_map, text="Next Tab (RB)").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        ttk.Entry(input_map, textvariable=self.btn_tab_next_var, width=6).grid(row=1, column=1, padx=6, pady=6)
        ttk.Label(input_map, text="Prev Tab (LB)").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        ttk.Entry(input_map, textvariable=self.btn_tab_prev_var, width=6).grid(row=1, column=3, padx=6, pady=6)

        analog = ttk.LabelFrame(frame, text="Analog Settings")
        analog.pack(fill="x", pady=6)
        ttk.Label(analog, text="Deadzone").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Scale(analog, from_=0.1, to=0.9, variable=self.deadzone_var, orient="horizontal").grid(
            row=0, column=1, padx=6, pady=6, sticky="ew"
        )
        ttk.Label(analog, text="Repeat ms").grid(row=0, column=2, padx=6, pady=6)
        ttk.Entry(analog, textvariable=self.repeat_ms_var, width=8).grid(row=0, column=3, padx=6, pady=6)
        analog.columnconfigure(1, weight=1)

        display = ttk.LabelFrame(frame, text="Display Settings")
        display.pack(fill="x", pady=6)
        self.resolutions = self._detect_resolutions()
        if self.resolution_var.get() and self.resolution_var.get() not in self.resolutions:
            self.resolutions.append(self.resolution_var.get())

        ttk.Label(display, text="Resolution").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.resolution_combo = ttk.Combobox(
            display,
            textvariable=self.resolution_var,
            values=self.resolutions,
            width=22,
        )
        self.resolution_combo.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        ttk.Button(display, text="Apply", command=self._apply_resolution).grid(row=0, column=2, padx=6, pady=6)
        ttk.Button(display, text="Refresh List", command=self._refresh_resolutions).grid(row=0, column=3, padx=6, pady=6)

    def _build_app_tab(self) -> None:
        self._build_tab_header(self.app_tab)
        app_settings = self.settings["app"]
        self.emulator_cmd_var = tk.StringVar(value=app_settings.get("emulator_command", ""))
        self.branch_var = tk.StringVar(value=app_settings.get("git_branch", "main"))
        self.auto_sync_var = tk.BooleanVar(value=bool(app_settings.get("auto_git_sync", True)))
        self.version_var = tk.StringVar(value=self._read_version())

        frame = ttk.Frame(self.app_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        info = ttk.LabelFrame(frame, text="Runtime")
        info.pack(fill="x", pady=6)
        ttk.Label(info, text=f"Version: {self.version_var.get()}").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Label(info, text=f"Install Path: {ACTIVE_ROOT}").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(info, text=f"Data Path: {DATA_DIR}").grid(row=2, column=0, sticky="w", padx=6, pady=2)
        repo = read_env_value("GITHUB_REPO") or "Not configured in .env"
        ttk.Label(info, text=f"Git Repo: {repo}").grid(row=3, column=0, sticky="w", padx=6, pady=2)

        exec_box = ttk.LabelFrame(frame, text="Launcher Settings")
        exec_box.pack(fill="x", pady=6)
        ttk.Label(exec_box, text="FCEUX Command").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(exec_box, textvariable=self.emulator_cmd_var, width=110).grid(
            row=0, column=1, sticky="ew", padx=6, pady=6
        )
        ttk.Label(exec_box, text="Git Branch").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(exec_box, textvariable=self.branch_var, width=24).grid(row=1, column=1, sticky="w", padx=6, pady=6)
        ttk.Checkbutton(exec_box, text="Enable auto git sync", variable=self.auto_sync_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6
        )
        exec_box.columnconfigure(1, weight=1)

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="Turnkey Setup", command=self._run_turnkey_setup).pack(side="left", padx=4)
        ttk.Button(actions, text="Run Updater", command=self._run_updater).pack(side="left", padx=4)
        ttk.Button(actions, text="Run App Script", command=self._run_launcher).pack(side="left", padx=4)
        ttk.Button(actions, text="Open Data Folder", command=lambda: self._open_path(DATA_DIR)).pack(side="left", padx=4)

        links_box = ttk.LabelFrame(frame, text="Required File Links")
        links_box.pack(fill="both", expand=True, pady=6)
        self.links_tree = ttk.Treeview(links_box, columns=("name", "url"), show="headings", height=8)
        self.links_tree.heading("name", text="Name")
        self.links_tree.heading("url", text="URL")
        self.links_tree.column("name", width=220, anchor="w")
        self.links_tree.column("url", width=850, anchor="w")
        self.links_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.links_tree.bind("<Double-1>", lambda _: self._open_selected_link())

        for name, url in app_settings.get("resource_links", {}).items():
            self.links_tree.insert("", "end", values=(name, url))
        ttk.Button(links_box, text="Open Selected Link", command=self._open_selected_link).pack(padx=6, pady=6, anchor="w")

    def _build_scores_tab(self) -> None:
        self._build_tab_header(self.scores_tab)
        frame = ttk.Frame(self.scores_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=8)

        self.score_name_var = tk.StringVar(value="")
        self.score_game_var = tk.StringVar(value="")
        self.score_value_var = tk.StringVar(value="")

        form = ttk.LabelFrame(frame, text="Add High Score")
        form.pack(fill="x", pady=6)
        ttk.Label(form, text="Name").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ttk.Entry(form, textvariable=self.score_name_var, width=20).grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(form, text="Score").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ttk.Entry(form, textvariable=self.score_value_var, width=12).grid(row=0, column=3, padx=6, pady=6)
        ttk.Label(form, text="Game").grid(row=0, column=4, padx=6, pady=6, sticky="w")
        ttk.Entry(form, textvariable=self.score_game_var, width=35).grid(row=0, column=5, padx=6, pady=6)
        ttk.Button(form, text="Add Score", command=self._add_score).grid(row=0, column=6, padx=8, pady=6)

        export_bar = ttk.Frame(frame)
        export_bar.pack(fill="x", pady=4)
        ttk.Button(export_bar, text="Export Excel + CSV", command=self._export_scores).pack(side="left", padx=4)
        ttk.Label(export_bar, text=f"Excel File: {HIGHSCORE_XLSX}").pack(side="left", padx=8)

        self.score_tree = ttk.Treeview(frame, columns=("score", "name", "time", "game"), show="headings")
        self.score_tree.heading("score", text="Score")
        self.score_tree.heading("name", text="Name")
        self.score_tree.heading("time", text="Time")
        self.score_tree.heading("game", text="Game Name")
        self.score_tree.column("score", width=90, anchor="e")
        self.score_tree.column("name", width=180, anchor="w")
        self.score_tree.column("time", width=180, anchor="w")
        self.score_tree.column("game", width=320, anchor="w")
        self.score_tree.pack(fill="both", expand=True, pady=8)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        self.logger.info(message)

    def _append_error_log(self, title: str, details: str) -> None:
        try:
            LOG_APP_DIR.mkdir(parents=True, exist_ok=True)
            error_file = LOG_APP_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
            with error_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {title}\n")
                handle.write(f"{details}\n\n")
            self.logger.error("%s | %s", title, details)
        except Exception as exc:
            self.logger.error("Failed writing error log: %s", exc)

    def _pick_folder(self, var: tk.StringVar) -> None:
        picked = filedialog.askdirectory(initialdir=var.get() or str(ACTIVE_ROOT))
        if picked:
            var.set(picked)
            self._load_games()

    def _load_games(self) -> None:
        rom_dir = Path(self.rom_dir_var.get()).expanduser()
        image_dir = Path(self.image_dir_var.get()).expanduser()
        extensions = tuple(ext.lower() for ext in self.settings["library"].get("rom_extensions", []))
        show_scheduled_only = self.show_scheduled_only_var.get()
        sort_mode = self.sort_mode_var.get()

        self.games = []
        self.game_list.delete(0, tk.END)
        if not rom_dir.exists():
            self._set_status(f"ROM folder not found: {rom_dir}")
            return

        for candidate in rom_dir.iterdir():
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in extensions:
                continue
            key = candidate.stem
            schedule = self.settings["game_schedules"].get(key, {})
            if show_scheduled_only and not schedule.get("enabled", False):
                continue
            image_path = self._find_image_path(image_dir, key)
            stat = candidate.stat()
            self.games.append(
                {
                    "name": key,
                    "rom": str(candidate),
                    "image": str(image_path) if image_path else "",
                    "ctime": stat.st_ctime,
                }
            )

        if sort_mode == "Name (A-Z)":
            self.games.sort(key=lambda x: x["name"].lower())
        elif sort_mode == "Install Date (Oldest)":
            self.games.sort(key=lambda x: x["ctime"])
        else:
            self.games.sort(key=lambda x: x["ctime"], reverse=True)

        for entry in self.games:
            self.game_list.insert(tk.END, entry["name"])

        self._set_status(f"Loaded {len(self.games)} game(s)")

    def _find_image_path(self, image_dir: Path, base_name: str) -> Path | None:
        for ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            candidate = image_dir / f"{base_name}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _on_game_selected(self, _event: Any) -> None:
        game = self._get_selected_game()
        if not game:
            return
        self.score_game_var.set(game["name"])
        self._load_schedule_for_game(game["name"])
        self._update_preview(game.get("image", ""))

    def _update_preview(self, image_path: str) -> None:
        if not image_path or not Path(image_path).exists():
            self.preview_image = None
            self.preview_label.configure(image="", text="No artwork found for selected ROM")
            return
        if Image is None or ImageTk is None:
            self.preview_image = None
            self.preview_label.configure(image="", text=f"Artwork exists: {image_path}\nInstall Pillow for preview")
            return
        try:
            img = Image.open(image_path)
            img.thumbnail((640, 420))
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.preview_image, text="")
        except Exception as exc:
            self.preview_image = None
            self.preview_label.configure(image="", text=f"Image load failed: {exc}")

    def _get_selected_game(self) -> dict[str, Any] | None:
        selected = self.game_list.curselection()
        if not selected:
            return None
        idx = int(selected[0])
        if idx < 0 or idx >= len(self.games):
            return None
        return self.games[idx]

    def _load_schedule_for_game(self, game_name: str) -> None:
        schedule = self.settings["game_schedules"].get(game_name, {})
        self.schedule_enabled_var.set(bool(schedule.get("enabled", False)))
        self.schedule_start_var.set(schedule.get("start", "08:00"))
        self.schedule_end_var.set(schedule.get("end", "23:00"))
        selected_days = set(int(day) for day in schedule.get("days", list(range(7))))
        for idx in range(7):
            self.day_vars[idx].set(idx in selected_days)

    def _apply_schedule_to_selected(self) -> None:
        game = self._get_selected_game()
        if not game:
            messagebox.showinfo("No Game", "Select a game first.")
            return
        if not self._valid_hhmm(self.schedule_start_var.get()) or not self._valid_hhmm(self.schedule_end_var.get()):
            messagebox.showerror("Invalid Time", "Use HH:MM format for schedule times.")
            return
        self.settings["game_schedules"][game["name"]] = {
            "enabled": self.schedule_enabled_var.get(),
            "start": self.schedule_start_var.get(),
            "end": self.schedule_end_var.get(),
            "days": [idx for idx, var in enumerate(self.day_vars) if var.get()],
        }
        self._set_status(f"Schedule set for {game['name']} (save settings to persist)")

    @staticmethod
    def _valid_hhmm(value: str) -> bool:
        if not re.match(r"^\d{2}:\d{2}$", value):
            return False
        hh, mm = value.split(":")
        return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59

    def launch_selected_game(self) -> None:
        game = self._get_selected_game()
        if not game:
            messagebox.showinfo("No Game", "Select a game to launch.")
            return
        if not self._launch_allowed(game["name"]):
            messagebox.showwarning("Blocked By Schedule", f"{game['name']} is outside allowed launch schedule.")
            return

        try:
            launch_args, launch_text = self._build_launch_command(game["rom"])
            self.logger.info("Launching game '%s' with command: %s", game["name"], launch_text)
            process = subprocess.Popen(launch_args, shell=False)
            self._set_status(f"Launch requested for {game['name']}")
            self._monitor_launch_process(game["name"], process, launch_text)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}\nROM: {game.get('rom', '')}\nTrace:\n{traceback.format_exc()}"
            self._append_error_log("launch-failed", detail)
            messagebox.showerror("Launch Failed", str(exc))
            self._set_status(f"Launch failed: {exc}")

    def _build_launch_command(self, rom_path: str) -> tuple[list[str], str]:
        rom_file = Path(rom_path)
        if not rom_file.exists():
            raise FileNotFoundError(f"ROM file not found: {rom_path}")

        cmd_template = self.emulator_cmd_var.get().strip()
        if not cmd_template:
            cmd_template = self._default_emulator_command(self._find_fceux_executable())
        command_text = cmd_template.format(rom=rom_path)
        try:
            args = shlex.split(command_text, posix=(os.name != "nt"))
        except Exception:
            args = [command_text]

        if os.name == "nt":
            normalized: list[str] = []
            for arg in args:
                cleaned = arg.strip()
                if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] == '"':
                    cleaned = cleaned[1:-1]
                normalized.append(cleaned)
            args = normalized

        if not args:
            raise RuntimeError("Emulator command is empty.")

        executable = args[0]
        exists = Path(executable).exists() or bool(shutil.which(executable))
        if not exists and "fceux" in executable.lower():
            detected = self._find_fceux_executable()
            if detected:
                args[0] = detected
                command_text = subprocess.list2cmdline(args) if os.name == "nt" else " ".join(args)
            else:
                raise FileNotFoundError(
                    "FCEUX executable not found. Run Windows updater/full install, then click Turnkey Setup."
                )
        if os.name == "nt":
            command_text = subprocess.list2cmdline(args)
        return args, command_text

    def _monitor_launch_process(self, game_name: str, process: subprocess.Popen[Any], launch_text: str) -> None:
        def _watch() -> None:
            time.sleep(1.5)
            rc = process.poll()
            if rc is None:
                return
            message = f"{game_name} closed immediately (exit code {rc})."
            self.logger.warning("Launch exited quickly (%s): %s | %s", rc, game_name, launch_text)
            self._append_error_log(
                "launch-exited-quickly",
                f"game={game_name}\nexit_code={rc}\ncommand={launch_text}",
            )
            self.root.after(
                0,
                lambda: messagebox.showwarning(
                    "Game Launch Warning",
                    f"{message}\nCheck emulator command and ROM compatibility.\n\nCommand:\n{launch_text}",
                ),
            )
            self.root.after(0, lambda: self._set_status(message))

        threading.Thread(target=_watch, daemon=True).start()

    def _launch_allowed(self, game_name: str) -> bool:
        schedule = self.settings["game_schedules"].get(game_name, {})
        if not schedule.get("enabled", False):
            return True
        try:
            now = datetime.now()
            current_day = now.weekday()
            allowed_days = set(int(day) for day in schedule.get("days", []))
            if current_day not in allowed_days:
                return False
            start_h, start_m = [int(x) for x in str(schedule.get("start", "00:00")).split(":", 1)]
            end_h, end_m = [int(x) for x in str(schedule.get("end", "23:59")).split(":", 1)]
            now_minutes = now.hour * 60 + now.minute
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            if start_minutes <= end_minutes:
                return start_minutes <= now_minutes <= end_minutes
            return now_minutes >= start_minutes or now_minutes <= end_minutes
        except Exception:
            return True

    def _run_shell(self, command: str) -> None:
        cmd = command.strip()
        if not cmd:
            messagebox.showinfo("Missing Command", "Add a command first.")
            return
        try:
            subprocess.Popen(cmd, shell=True)
            self._set_status(f"Executed: {cmd}")
        except Exception as exc:
            messagebox.showerror("Command Failed", str(exc))

    def _detect_resolutions(self) -> list[str]:
        if os.name != "posix":
            return []
        try:
            output = subprocess.run(["xrandr", "--query"], check=False, capture_output=True, text=True).stdout
        except Exception:
            return []
        found: list[str] = []
        for line in output.splitlines():
            match = re.search(r"^\s+(\d+x\d+)\s", line)
            if match:
                val = match.group(1)
                if val not in found:
                    found.append(val)
        return found

    def _refresh_resolutions(self) -> None:
        self.resolutions = self._detect_resolutions()
        self.resolution_combo.configure(values=self.resolutions)
        self._set_status(f"Detected {len(self.resolutions)} display mode(s)")

    def _apply_resolution(self) -> None:
        value = self.resolution_var.get().strip()
        if not value:
            return
        if os.name == "nt":
            self._set_status("Windows resolution changes are not applied automatically from this app.")
            return
        try:
            subprocess.run(["xrandr", "--size", value], check=False)
            self._set_status(f"Resolution apply command sent: {value}")
        except Exception as exc:
            messagebox.showerror("Resolution Error", str(exc))

    def _open_selected_link(self) -> None:
        selected = self.links_tree.selection()
        if not selected:
            return
        _name, url = self.links_tree.item(selected[0], "values")
        webbrowser.open(url)

    def _run_turnkey_setup(self) -> None:
        self._apply_turnkey_defaults()
        self.settings = self.settings_store.load()
        self.emulator_cmd_var.set(self.settings["app"].get("emulator_command", ""))
        self.rom_dir_var.set(self.settings["library"].get("rom_dir", str(ACTIVE_ROOT / "roms")))
        self.image_dir_var.set(self.settings["library"].get("image_dir", str(ACTIVE_ROOT / "roms")))
        self.calibration_cmd_var.set(self.settings["sinden"].get("calibration_command", ""))
        self.button_cfg_cmd_var.set(self.settings["sinden"].get("button_config_command", ""))
        self.diagnostics_cmd_var.set(self.settings["sinden"].get("diagnostics_command", ""))
        self._load_games()
        self._set_status("Turnkey defaults applied")

    def _run_updater(self) -> None:
        if not UPDATE_SCRIPT.exists():
            messagebox.showerror("Missing Updater", f"Updater not found: {UPDATE_SCRIPT}")
            return
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UPDATE_SCRIPT)]
                )
            else:
                subprocess.Popen(["bash", str(UPDATE_SCRIPT)])
            self._set_status("Updater started")
        except Exception as exc:
            messagebox.showerror("Updater Failed", str(exc))

    def _run_launcher(self) -> None:
        if not RUN_SCRIPT.exists():
            messagebox.showerror("Missing Launcher", f"Launcher not found: {RUN_SCRIPT}")
            return
        try:
            if os.name == "nt":
                subprocess.Popen(["cmd.exe", "/c", str(RUN_SCRIPT)])
            else:
                subprocess.Popen(["bash", str(RUN_SCRIPT)])
            self._set_status("Launcher started")
        except Exception as exc:
            messagebox.showerror("Launcher Failed", str(exc))

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open Path Failed", str(exc))

    def _add_score(self) -> None:
        name = self.score_name_var.get().strip()
        value = self.score_value_var.get().strip()
        game = self.score_game_var.get().strip()
        if not name or not value or not game:
            messagebox.showerror("Missing Fields", "Name, Score, and Game are required.")
            return
        try:
            score = int(value)
        except ValueError:
            messagebox.showerror("Invalid Score", "Score must be a number.")
            return
        self.high_scores.add_score(score=score, name=name, game_name=game)
        self._export_scores(silent=True)
        self._refresh_high_scores()
        self.score_value_var.set("")
        self._set_status(f"High score saved for {name} ({score})")
        if self.auto_sync_var.get():
            trigger_auto_sync("high-score-update", self.branch_var.get().strip() or "main", self.logger)

    def _refresh_high_scores(self) -> None:
        for row in self.score_tree.get_children():
            self.score_tree.delete(row)
        for entry in self.high_scores.get_scores(limit=250):
            self.score_tree.insert("", "end", values=(entry.score, entry.name, entry.played_at, entry.game_name))

    def _export_scores(self, silent: bool = False) -> None:
        xlsx_path, csv_path = self.high_scores.export_all()
        if not silent:
            messagebox.showinfo("Export Complete", f"Saved:\n{xlsx_path}\n{csv_path}")
        self._set_status(f"High scores exported to {xlsx_path.name} and {csv_path.name}")

    def save_all_settings(self) -> None:
        library = self.settings["library"]
        library["rom_dir"] = self.rom_dir_var.get().strip()
        library["image_dir"] = self.image_dir_var.get().strip()
        library["show_scheduled_only"] = bool(self.show_scheduled_only_var.get())
        library["sort_mode"] = self.sort_mode_var.get().strip()

        sinden = self.settings["sinden"]
        sinden["calibration_command"] = self.calibration_cmd_var.get().strip()
        sinden["button_config_command"] = self.button_cfg_cmd_var.get().strip()
        sinden["diagnostics_command"] = self.diagnostics_cmd_var.get().strip()
        sinden["screen_width"] = int(self.screen_width_var.get())
        sinden["screen_height"] = int(self.screen_height_var.get())

        controller = self.settings["controller"]
        controller["deadzone"] = float(self.deadzone_var.get())
        controller["repeat_ms"] = int(self.repeat_ms_var.get())
        controller["resolution"] = self.resolution_var.get().strip()
        controller["button_map"] = {
            "select": int(self.btn_select_var.get()),
            "back": int(self.btn_back_var.get()),
            "tab_next": int(self.btn_tab_next_var.get()),
            "tab_prev": int(self.btn_tab_prev_var.get()),
        }

        app_settings = self.settings["app"]
        app_settings["emulator_command"] = self.emulator_cmd_var.get().strip()
        app_settings["git_branch"] = self.branch_var.get().strip() or "main"
        app_settings["auto_git_sync"] = bool(self.auto_sync_var.get())

        self.settings_store.save()
        self._set_status("Settings saved")
        self._restart_controller()
        self._load_games()
        if self.auto_sync_var.get():
            trigger_auto_sync("settings-save", self.branch_var.get().strip() or "main", self.logger)

    def _restart_controller(self) -> None:
        self.controller.stop()
        self.controller = ControllerInput(self.action_queue, self.settings["controller"], self.logger)
        self.controller.start()

    def _poll_controller_actions(self) -> None:
        while True:
            try:
                action = self.action_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_action(action)
        self.root.after(80, self._poll_controller_actions)

    def _handle_action(self, action: str) -> None:
        if action in {"right", "tab_next"}:
            idx = self.notebook.index(self.notebook.select())
            count = len(self.notebook.tabs())
            self.notebook.select((idx + 1) % count)
            return
        if action in {"left", "tab_prev"}:
            idx = self.notebook.index(self.notebook.select())
            count = len(self.notebook.tabs())
            self.notebook.select((idx - 1) % count)
            return

        current_tab = self.notebook.nametowidget(self.notebook.select())
        if current_tab is self.library_tab:
            if action == "up":
                self._move_game_selection(-1)
            elif action == "down":
                self._move_game_selection(1)
            elif action == "select":
                self.launch_selected_game()
        elif current_tab is self.scores_tab and action == "select":
            self._add_score()

        if action == "back":
            self.notebook.select(0)

    def _move_game_selection(self, delta: int) -> None:
        if not self.games:
            return
        selected = self.game_list.curselection()
        idx = int(selected[0]) if selected else 0
        target = max(0, min(len(self.games) - 1, idx + delta))
        self.game_list.selection_clear(0, tk.END)
        self.game_list.selection_set(target)
        self.game_list.activate(target)
        self.game_list.see(target)
        self._on_game_selected(None)

    def _on_close(self) -> None:
        try:
            self.controller.stop()
        finally:
            self.root.destroy()
