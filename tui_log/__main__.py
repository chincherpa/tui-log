"""
tui_log/__main__.py
~~~~~~~~~~~~~~~~~~~~
Einstiegspunkt – startet die Work-TUI.

Optionen:
  --config PATH   Alternative config.toml
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig
from .schema import init_db
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


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="python work_app.py",
        description="Strukturiertes Tagesjournal fürs Terminal.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Alternative config.toml",
    )
    return parser.parse_args()


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

    # 3. App starten
    from .work_app import WorkApp
    try:
        WorkApp(cfg).run()
    except Exception as e:
        logging.error(f"Unbehandelter Fehler:\n{traceback.format_exc()}")
        print(f"\n[Fehler] {e}\nDetails in: {log_path}")

    # 4. WAL-Checkpoint: -shm und -wal Dateien aufräumen
    _wal_cleanup(cfg.db_path)


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


if __name__ == "__main__":
    main()
