"""
tui_log/schema.py
~~~~~~~~~~~~~~~~~
SQLite-Schema für tui-log.
Migrationsbasiert – jede Version ist idempotent ausführbar.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Aktuelle Schema-Version – erhöhen wenn neue Migration hinzukommt
SCHEMA_VERSION = 2

# ── SQL ──────────────────────────────────────────────────────────────────────

_MIGRATIONS: dict[int, str] = {

    1: """
    -- ── Metadaten ────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL,
        applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- ── Tages-Log ─────────────────────────────────────────────────────────
    -- Ein Eintrag = eine geloggte Aktivität (schnell, mit Tag)
    CREATE TABLE IF NOT EXISTS log_entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,               -- ISO: 2026-03-31
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        tag_key     TEXT    NOT NULL,               -- z.B. "done", "block"
        mode        TEXT    NOT NULL DEFAULT 'work', -- work|family|weekend
        content     TEXT    NOT NULL,
        todo_id     INTEGER REFERENCES todos(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_log_date ON log_entries(date);
    CREATE INDEX IF NOT EXISTS idx_log_tag  ON log_entries(tag_key);

    -- ── Tagesstruktur ─────────────────────────────────────────────────────
    -- Morgen-/Abend-Ritual und Tagesbewertung
    CREATE TABLE IF NOT EXISTS day_meta (
        date            TEXT PRIMARY KEY,           -- ISO: 2026-03-31
        mode            TEXT NOT NULL DEFAULT 'work', -- work|weekend
        morning_focus   TEXT,                       -- Fokus des Tages
        morning_energy  INTEGER CHECK(morning_energy BETWEEN 1 AND 5),
        evening_done    TEXT,                       -- Was fertig wurde
        evening_open    TEXT,                       -- Carry-over für morgen
        day_rating      TEXT CHECK(day_rating IN ('zaeh','ok','gut','sehr_gut')),
        evening_note    TEXT,
        work_locked     INTEGER NOT NULL DEFAULT 0  -- 1 nach Feierabend-Ritual
    );

    -- ── Todos ─────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS todos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        context     TEXT,                           -- z.B. "dashboard-local"
        status      TEXT    NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','active','paused','done','dropped')),
        priority    TEXT    NOT NULL DEFAULT 'normal'
                    CHECK(priority IN ('high','normal','low')),
        mode        TEXT    NOT NULL DEFAULT 'work' -- work|weekend|any
                    CHECK(mode IN ('work','weekend','any')),
        tags        TEXT,                           -- JSON-Array: ["work","idea"]
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        done_at     TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_todo_status ON todos(status);
    CREATE INDEX IF NOT EXISTS idx_todo_mode   ON todos(mode);

    -- ── Focus-Sessions ────────────────────────────────────────────────────
    -- Eine Session = ein Zeitblock in dem an einem Todo gearbeitet wurde
    CREATE TABLE IF NOT EXISTS focus_sessions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        todo_id     INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
        started_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        ended_at    TEXT,
        duration_s  INTEGER,                        -- NULL bis Session endet
        timer_preset TEXT,                          -- "25"|"45"|"90"|"open"
        outcome     TEXT CHECK(outcome IN ('solved','open','blocked', NULL)),
        log_entry   TEXT                            -- Auto-Text fürs Tages-Log
    );

    CREATE INDEX IF NOT EXISTS idx_session_todo ON focus_sessions(todo_id);

    -- ── Todo-Notizen ──────────────────────────────────────────────────────
    -- Freie Notizen während einer Focus-Session (mit SPACE eingeworfen)
    CREATE TABLE IF NOT EXISTS todo_notes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        todo_id     INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
        session_id  INTEGER REFERENCES focus_sessions(id) ON DELETE SET NULL,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        content     TEXT    NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_note_todo    ON todo_notes(todo_id);
    CREATE INDEX IF NOT EXISTS idx_note_session ON todo_notes(session_id);

    -- ── Wochenend-Projekte ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS projects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL UNIQUE,
        tag_key     TEXT,                           -- z.B. "bau", "gart"
        phase       TEXT    NOT NULL DEFAULT 'active'
                    CHECK(phase IN ('planning','active','paused','done')),
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        done_at     TEXT
    );
    """,

    2: """
    -- Blockierungen können als aufgelöst markiert werden
    ALTER TABLE log_entries ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0;

    -- Nur eine gleichzeitig laufende Focus-Session erlauben
    CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_session
    ON focus_sessions((1)) WHERE ended_at IS NULL;
    """,
}

# ── Verbindung ────────────────────────────────────────────────────────────────

@contextmanager
def get_connection(db_path: Path, readonly: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """
    Context-Manager für SQLite-Verbindungen.
    - WAL-Mode für bessere Concurrent-Reads
    - Row-Factory für dict-ähnlichen Zugriff
    - Auto-Commit oder Rollback bei Exception
    """
    base_uri = db_path.resolve().as_uri()
    uri = f"{base_uri}?mode=ro" if readonly else base_uri
    conn = sqlite3.connect(uri, uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=3000")
    try:
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            conn.rollback()
        raise
    finally:
        conn.close()

# ── Migration ─────────────────────────────────────────────────────────────────

def _exec_migration_sql(conn: sqlite3.Connection, sql: str) -> None:
    """
    Führt ein Multi-Statement-Migrations-SQL innerhalb der laufenden Transaktion aus.
    Im Gegensatz zu executescript() wird kein implizites COMMIT vorher durchgeführt,
    sodass DDL + schema_version INSERT atomar committ werden.
    """
    for stmt in (s.strip() for s in sql.split(";")):
        # Leere Statements und reine Kommentar-Blöcke überspringen
        code = "\n".join(
            line for line in stmt.splitlines()
            if line.strip() and not line.strip().startswith("--")
        )
        if code:
            conn.execute(stmt)


def _current_version(conn: sqlite3.Connection) -> int:
    """Aktuelle Schema-Version aus DB lesen (0 wenn frisch)."""
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0

def migrate(db_path: Path) -> int:
    """
    Führt ausstehende Migrationen aus.
    Gibt die neue Schema-Version zurück.

    Idempotent: bereits angewendete Versionen werden übersprungen.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        current = _current_version(conn)

        applied = 0
        for version, sql in sorted(_MIGRATIONS.items()):
            if version <= current:
                continue
            _exec_migration_sql(conn, sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            applied += 1

        new_version = _current_version(conn)

    return new_version

def init_db(db_path: Path) -> Path:
    """
    Shortcut: DB initialisieren/migrieren und Pfad zurückgeben.
    Wirft bei Fehler eine aussagekräftige Exception.
    """
    try:
        version = migrate(db_path)
        return db_path
    except sqlite3.Error as e:
        raise RuntimeError(f"DB-Initialisierung fehlgeschlagen ({db_path}): {e}") from e
