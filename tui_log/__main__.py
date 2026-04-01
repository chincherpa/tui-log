"""
tui_log/__main__.py
~~~~~~~~~~~~~~~~~~~~
Einstiegspunkt – erkennt Modus und startet die passende TUI.

Optionen:
  --mode work|family|weekend   Modus erzwingen
  --config PATH                Alternative config.toml

Modus wechseln per Shortcuts (aus jeder App heraus):
  Ctrl+A  →  Arbeit (Work)
  Ctrl+F  →  Familie
  Ctrl+W  →  Wochenende
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig
from .schema import init_db
from .mode import detect_mode, Mode
from . import db_utils as db

import logging
import traceback

def _setup_logging(log_path: Path) -> None:
    """Schreibt alle Exceptions in tui-log.log neben der DB."""
    logging.basicConfig(
        filename=str(log_path),
        level=logging.ERROR,
        format="%(asctime)s  %(levelname)s  %(message)s",
    )

VALID_MODES = {"work", "family", "weekend"}


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="python -m tui_log",
        description="Strukturiertes Tagesjournal fürs Terminal.",
    )
    parser.add_argument(
        "--mode",
        choices=list(VALID_MODES),
        default=None,
        metavar="MODE",
        help="Modus erzwingen: work | family | weekend",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Alternative config.toml",
    )
    return parser.parse_args()


def _run_mode(mode: str, cfg: AppConfig) -> str | None:
    """
    Startet die TUI für den gegebenen Modus.
    Gibt den Ziel-Modus zurück wenn der Nutzer per Ctrl+A/F/W wechselt,
    sonst None (normales Beenden).
    """
    if mode == "work":
        from .work_app import WorkApp
        result = WorkApp(cfg).run()
    elif mode == "weekend":
        from .modes.weekend import WeekendApp
        result = WeekendApp(cfg).run()
    else:
        from .modes.family import FamilyApp
        result = FamilyApp(cfg).run()

    # Textual gibt den Wert aus self.exit(value) zurück
    return result if result in VALID_MODES else None


def main() -> None:
    args = _parse_args()

    # 1. Config laden
    config_path = Path(args.config) if args.config else None
    try:
        cfg = AppConfig.load(config_path)
    except FileNotFoundError as e:
        print(f"[Fehler] {e}")
        raise SystemExit(1)

    # 2. DB initialisieren
    try:
        init_db(cfg.db_path)
    except RuntimeError as e:
        print(f"[Fehler] {e}")
        raise SystemExit(1)

    log_path = cfg.db_path.parent / "tui-log.log"
    _setup_logging(log_path)

    db.project_upsert_from_config(cfg.db_path, cfg.projects)

    # 3. Startmodus bestimmen
    if args.mode:
        current_mode = args.mode
    else:
        detected = detect_mode(cfg.schedule)
        current_mode = {
            Mode.WORK:     "work",
            Mode.HANDOVER: "work",
            Mode.FAMILY:   "family",
            Mode.WEEKEND:  "weekend",
        }[detected]

    # 4. App-Loop – läuft bis Nutzer [q] drückt (kein Moduswechsel)
    while current_mode is not None:
        try:
            next_mode = _run_mode(current_mode, cfg)
        except Exception as e:
            logging.error(f"Unbehandelter Fehler im Modus '{current_mode}':\n{traceback.format_exc()}")
            print(f"\n[Fehler] {e}\nDetails in: {log_path}")
            break
        current_mode = next_mode

    # 5. WAL-Checkpoint: -shm und -wal Dateien aufräumen
    _wal_cleanup(cfg.db_path)


if __name__ == "__main__":
    main()


def _wal_cleanup(db_path: Path) -> None:
    """
    WAL-Checkpoint nach App-Exit.
    TRUNCATE schreibt alle WAL-Seiten in die Hauptdatei und leert die WAL,
    sodass SQLite die .wal und .shm Dateien beim nächsten Close entfernt.
    """
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass   # Nicht kritisch – beim nächsten Start wird es nachgeholt
