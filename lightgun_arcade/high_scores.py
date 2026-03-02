from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .paths import HIGHSCORE_DB, HIGHSCORE_XLSX

try:
    from openpyxl import Workbook
except Exception:  # pragma: no cover - optional import fallback
    Workbook = None


@dataclass
class HighScore:
    score: int
    name: str
    played_at: str
    game_name: str


class HighScoreStore:
    def __init__(self, db_path: Path = HIGHSCORE_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS high_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    score INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    played_at TEXT NOT NULL,
                    game_name TEXT NOT NULL
                )
                """
            )
            con.commit()

    def add_score(self, score: int, name: str, game_name: str, played_at: str | None = None) -> None:
        played = played_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as con:
            con.execute(
                "INSERT INTO high_scores(score, name, played_at, game_name) VALUES(?, ?, ?, ?)",
                (score, name.strip(), played, game_name.strip()),
            )
            con.commit()

    def get_scores(self, limit: int = 250) -> list[HighScore]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT score, name, played_at, game_name
                FROM high_scores
                ORDER BY score DESC, played_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [HighScore(int(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows]

    def export_all(self, xlsx_path: Path = HIGHSCORE_XLSX) -> tuple[Path, Path]:
        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path = xlsx_path.with_suffix(".csv")
        scores = self.get_scores(limit=5000)
        self._export_csv(csv_path, scores)
        if Workbook is not None:
            self._export_xlsx(xlsx_path, scores)
        return xlsx_path, csv_path

    @staticmethod
    def _export_csv(csv_path: Path, scores: Iterable[HighScore]) -> None:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Score", "Name", "Time", "Game Name"])
            for entry in scores:
                writer.writerow([entry.score, entry.name, entry.played_at, entry.game_name])

    @staticmethod
    def _export_xlsx(xlsx_path: Path, scores: Iterable[HighScore]) -> None:
        if Workbook is None:
            return
        book = Workbook()
        sheet = book.active
        sheet.title = "High Scores"
        sheet.append(["Score", "Name", "Time", "Game Name"])
        for entry in scores:
            sheet.append([entry.score, entry.name, entry.played_at, entry.game_name])
        book.save(xlsx_path)

