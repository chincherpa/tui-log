"""
tui_log/db_utils.py
~~~~~~~~~~~~~~~~~~~
CRUD-Funktionen für alle Tabellen.

Konventionen:
  - Alle Funktionen nehmen db_path: Path als erstes Argument
  - Rückgabe: dataclass | list[dataclass] | None  (nie rohe sqlite3.Row)
  - Timestamps immer als ISO-String (localtime)
  - Keine Business-Logik hier – nur DB-Operationen
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from .schema import get_connection

# ── Typen ─────────────────────────────────────────────────────────────────────

Status   = Literal["open", "active", "paused", "done", "dropped", "cancelled"]
Priority = Literal["high", "normal", "low"]
TodoMode = Literal["work"]
LogMode  = Literal["work"]
Outcome  = Literal["solved", "open", "blocked"]
Rating   = Literal["zaeh", "ok", "gut", "sehr_gut"]
Phase    = Literal["planning", "active", "paused", "done"]

def _today() -> str:
    return date.today().isoformat()

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Dataclasses (Row → Python) ────────────────────────────────────────────────

@dataclass
class LogEntry:
    id: int
    date: str
    created_at: str
    tag_key: str
    mode: str
    content: str
    todo_id: int | None = None
    resolved: int = 0

@dataclass
class DayMeta:
    date: str
    mode: str
    morning_focus: str | None = None
    morning_energy: int | None = None
    evening_done: str | None = None
    evening_open: str | None = None
    day_rating: str | None = None
    evening_note: str | None = None
    work_locked: bool = False

@dataclass
class Todo:
    id: int
    title: str
    context: str | None
    status: str
    priority: str
    mode: str
    tags: list[str]
    created_at: str
    done_at: str | None
    # Aggregiert aus focus_sessions – optional befüllt
    total_sessions: int = 0
    total_duration_s: int = 0

@dataclass
class FocusSession:
    id: int
    todo_id: int
    started_at: str
    ended_at: str | None
    duration_s: int | None
    timer_preset: str | None
    outcome: str | None
    log_entry: str | None

@dataclass
class TodoNote:
    id: int
    todo_id: int
    session_id: int | None
    created_at: str
    content: str

@dataclass
class SubTodo:
    id: int
    todo_id: int
    title: str
    done: bool
    created_at: str

@dataclass
class Project:
    id: int
    name: str
    tag_key: str | None
    phase: str
    created_at: str
    done_at: str | None

# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_log(row) -> LogEntry:
    return LogEntry(**dict(row))

def _row_to_todo(row) -> Todo:
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d.get("tags") else []
    # Aggregierte Felder fehlen bei simplen SELECTs → Defaultwerte
    d.setdefault("total_sessions", 0)
    d.setdefault("total_duration_s", 0)
    return Todo(**d)

def _row_to_session(row) -> FocusSession:
    return FocusSession(**dict(row))

def _row_to_note(row) -> TodoNote:
    return TodoNote(**dict(row))

def _row_to_subtodo(row) -> SubTodo:
    d = dict(row)
    d["done"] = bool(d["done"])
    return SubTodo(**d)

def _row_to_project(row) -> Project:
    return Project(**dict(row))

def _row_to_day(row) -> DayMeta:
    d = dict(row)
    d["work_locked"] = bool(d["work_locked"])
    return DayMeta(**d)

# ─────────────────────────────────────────────────────────────────────────────
# LOG ENTRIES
# ─────────────────────────────────────────────────────────────────────────────

def log_add(
    db_path: Path,
    tag_key: str,
    content: str,
    mode: LogMode = "work",
    date_str: str | None = None,
    todo_id: int | None = None,
) -> LogEntry:
    """Neuen Log-Eintrag schreiben."""
    date_str = date_str or _today()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO log_entries (date, tag_key, mode, content, todo_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date_str, tag_key, mode, content.strip(), todo_id),
        )
        row_id = cur.lastrowid
    # Nach commit lesen – sonst sieht eine neue Readonly-Connection die Zeile nicht
    return log_get(db_path, row_id)  # type: ignore[return-value]

def log_get(db_path: Path, entry_id: int) -> LogEntry | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM log_entries WHERE id = ?", (entry_id,)
        ).fetchone()
    return _row_to_log(row) if row else None

def log_update(
    db_path: Path,
    entry_id: int,
    content: str | None = None,
    tag_key: str | None = None,
    resolved: int | None = None,
) -> LogEntry | None:
    """Aktualisiert Felder eines Log-Eintrags; nur übergebene Felder werden gesetzt."""
    fields: list[str] = []
    params: list = []
    if content is not None:
        fields.append("content = ?"); params.append(content.strip())
    if tag_key is not None:
        fields.append("tag_key = ?"); params.append(tag_key)
    if resolved is not None:
        fields.append("resolved = ?"); params.append(1 if resolved else 0)
    if not fields:
        return log_get(db_path, entry_id)
    params.append(entry_id)
    with get_connection(db_path) as conn:
        conn.execute(f"UPDATE log_entries SET {', '.join(fields)} WHERE id = ?", params)
    return log_get(db_path, entry_id)

def log_get_day(
    db_path: Path,
    date_str: str | None = None,
    mode: LogMode | None = None,
    tag_key: str | None = None,
) -> list[LogEntry]:
    """Alle Einträge eines Tages, optional nach Mode/Tag gefiltert."""
    date_str = date_str or _today()
    sql = "SELECT * FROM log_entries WHERE date = ?"
    params: list = [date_str]
    if mode:
        sql += " AND mode = ?"
        params.append(mode)
    if tag_key:
        sql += " AND tag_key = ?"
        params.append(tag_key)
    sql += " ORDER BY created_at"
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_log(r) for r in rows]

def log_get_range(
    db_path: Path,
    date_from: str,
    date_to: str,
    tag_key: str | None = None,
) -> list[LogEntry]:
    """Einträge in einem Datumsbereich."""
    sql = "SELECT * FROM log_entries WHERE date BETWEEN ? AND ?"
    params: list = [date_from, date_to]
    if tag_key:
        sql += " AND tag_key = ?"
        params.append(tag_key)
    sql += " ORDER BY date, created_at"
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_log(r) for r in rows]

def log_search(db_path: Path, query: str, limit: int = 50) -> list[LogEntry]:
    """Volltext-Suche im Log (LIKE)."""
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT * FROM log_entries
            WHERE content LIKE ?
            ORDER BY date DESC, created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()
    return [_row_to_log(r) for r in rows]

def log_delete(db_path: Path, entry_id: int) -> bool:
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))
    return cur.rowcount > 0

def log_get_all(
    db_path: Path,
    mode: LogMode | None = None,
) -> list[LogEntry]:
    """Alle Einträge, optional nach Mode gefiltert, neueste zuerst."""
    sql = "SELECT * FROM log_entries"
    params: list = []
    if mode:
        sql += " WHERE mode = ?"
        params.append(mode)
    sql += " ORDER BY date DESC, created_at DESC"
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_log(r) for r in rows]

def log_used_tags(db_path: Path, mode: LogMode | None = None) -> set[str]:
    """Distinct tag_keys die mindestens einen Log-Eintrag haben."""
    sql = "SELECT DISTINCT tag_key FROM log_entries"
    params: list = []
    if mode:
        sql += " WHERE mode = ?"
        params.append(mode)
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return {r["tag_key"] for r in rows}

def log_get_open_blocks(db_path: Path, before_date: str | None = None) -> list[LogEntry]:
    """
    [block]-Einträge die noch nicht als aufgelöst markiert wurden.
    Carry-over-Quelle für den Tagesstart.
    """
    before_date = before_date or _today()
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT * FROM log_entries
            WHERE tag_key = 'block'
              AND date < ?
              AND resolved = 0
            ORDER BY date DESC, created_at DESC
            """,
            (before_date,),
        ).fetchall()
    return [_row_to_log(r) for r in rows]

def log_resolve_block(db_path: Path, entry_id: int) -> bool:
    """Markiert einen [block]-Eintrag als aufgelöst (verschwindet aus dem Carry-Over)."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "UPDATE log_entries SET resolved = 1 WHERE id = ? AND tag_key = 'block'",
            (entry_id,),
        )
    return cur.rowcount > 0

# ─────────────────────────────────────────────────────────────────────────────
# DAY META
# ─────────────────────────────────────────────────────────────────────────────

def day_get(db_path: Path, date_str: str | None = None) -> DayMeta | None:
    date_str = date_str or _today()
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM day_meta WHERE date = ?", (date_str,)
        ).fetchone()
    return _row_to_day(row) if row else None

def day_get_or_create(db_path: Path, date_str: str | None = None, mode: LogMode = "work") -> DayMeta:
    """Holt oder erstellt DayMeta für ein Datum."""
    date_str = date_str or _today()
    existing = day_get(db_path, date_str)
    if existing:
        return existing
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO day_meta (date, mode) VALUES (?, ?)",
            (date_str, mode),
        )
    return day_get(db_path, date_str)  # type: ignore[return-value]

def day_set_morning(
    db_path: Path,
    focus: str,
    energy: int,
    date_str: str | None = None,
) -> DayMeta:
    """Optionale Tages-Metadaten (Fokus/Energie) speichern."""
    date_str = date_str or _today()
    day_get_or_create(db_path, date_str)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE day_meta
            SET morning_focus = ?, morning_energy = ?
            WHERE date = ?
            """,
            (focus.strip(), max(1, min(5, energy)), date_str),
        )
    return day_get(db_path, date_str)  # type: ignore[return-value]

def day_set_evening(
    db_path: Path,
    done: str,
    open_items: str,
    rating: Rating,
    note: str = "",
    date_str: str | None = None,
) -> DayMeta:
    """Feierabend-Ritual speichern und Arbeitsmodus sperren."""
    date_str = date_str or _today()
    day_get_or_create(db_path, date_str)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE day_meta
            SET evening_done = ?, evening_open = ?, day_rating = ?,
                evening_note = ?, work_locked = 1
            WHERE date = ?
            """,
            (done.strip(), open_items.strip(), rating, note.strip(), date_str),
        )
    return day_get(db_path, date_str)  # type: ignore[return-value]

def day_is_work_locked(db_path: Path, date_str: str | None = None) -> bool:
    meta = day_get(db_path, date_str or _today())
    return meta.work_locked if meta else False

def day_get_week(db_path: Path, iso_week: str) -> list[DayMeta]:
    """
    Alle DayMeta-Einträge einer ISO-Kalenderwoche.
    iso_week Format: "2026-W14"
    """
    date_from, date_to = _iso_week_to_date_range(iso_week)
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT * FROM day_meta
            WHERE date BETWEEN ? AND ?
            ORDER BY date
            """,
            (date_from, date_to),
        ).fetchall()
    return [_row_to_day(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# TODOS
# ─────────────────────────────────────────────────────────────────────────────

def todo_add(
    db_path: Path,
    title: str,
    context: str | None = None,
    priority: Priority = "normal",
    mode: TodoMode = "work",
    tags: list[str] | None = None,
) -> Todo:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO todos (title, context, priority, mode)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), context, priority, mode),
        )
        row_id = cur.lastrowid
    return todo_get(db_path, row_id)  # type: ignore[return-value]

def todo_get(db_path: Path, todo_id: int, with_stats: bool = True) -> Todo | None:
    with get_connection(db_path, readonly=True) as conn:
        if with_stats:
            row = conn.execute(
                """
                SELECT t.*,
                       COUNT(s.id)         AS total_sessions,
                       COALESCE(SUM(s.duration_s), 0) AS total_duration_s
                FROM todos t
                LEFT JOIN focus_sessions s ON s.todo_id = t.id
                WHERE t.id = ?
                GROUP BY t.id
                """,
                (todo_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM todos WHERE id = ?", (todo_id,)
            ).fetchone()
    return _row_to_todo(row) if row else None

def todo_list(
    db_path: Path,
    status: Status | None = None,
    mode: TodoMode | None = None,
    with_stats: bool = True,
) -> list[Todo]:
    """Todos nach Status und/oder Mode filtern."""
    conditions = []
    params: list = []
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if mode and mode != "any":
        conditions.append("(t.mode = ? OR t.mode = 'any')")
        params.append(mode)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    if with_stats:
        sql = f"""
            SELECT t.*,
                   COUNT(s.id)                    AS total_sessions,
                   COALESCE(SUM(s.duration_s), 0) AS total_duration_s
            FROM todos t
            LEFT JOIN focus_sessions s ON s.todo_id = t.id
            {where}
            GROUP BY t.id
            ORDER BY
                CASE t.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                t.created_at
        """
    else:
        sql = f"SELECT * FROM todos t {where} ORDER BY t.created_at"

    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_todo(r) for r in rows]

def todo_set_status(db_path: Path, todo_id: int, status: Status) -> Todo | None:
    done_at = _now() if status == "done" else None
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE todos SET status = ?, done_at = ? WHERE id = ?",
            (status, done_at, todo_id),
        )
    return todo_get(db_path, todo_id)

def todo_update(
    db_path: Path,
    todo_id: int,
    title: str | None = None,
    context: str | None = None,
    priority: Priority | None = None,
    mode: TodoMode | None = None,
    tags: list[str] | None = None,
) -> Todo | None:
    """Nur übergebene Felder aktualisieren."""
    fields, params = [], []
    if title is not None:
        fields.append("title = ?");    params.append(title.strip())
    if context is not None:
        fields.append("context = ?");  params.append(context)
    if priority is not None:
        fields.append("priority = ?"); params.append(priority)
    if mode is not None:
        fields.append("mode = ?");     params.append(mode)
    if tags is not None:
        fields.append("tags = ?");     params.append(json.dumps(tags))
    if not fields:
        return todo_get(db_path, todo_id)
    params.append(todo_id)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE todos SET {', '.join(fields)} WHERE id = ?", params
        )
    return todo_get(db_path, todo_id)

def todo_delete(db_path: Path, todo_id: int) -> bool:
    """Löscht Todo + verknüpfte Sessions/Notizen (CASCADE)."""
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    return cur.rowcount > 0

def todo_search(db_path: Path, query: str, limit: int = 20) -> list[Todo]:
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT t.*,
                   COUNT(s.id)                    AS total_sessions,
                   COALESCE(SUM(s.duration_s), 0) AS total_duration_s
            FROM todos t
            LEFT JOIN focus_sessions s ON s.todo_id = t.id
            WHERE t.title LIKE ? OR t.context LIKE ?
            GROUP BY t.id
            ORDER BY t.created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    return [_row_to_todo(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# FOCUS SESSIONS
# ─────────────────────────────────────────────────────────────────────────────

def session_start(
    db_path: Path,
    todo_id: int,
    timer_preset: str | None = None,
) -> FocusSession:
    """Session starten – setzt Todo auf 'active'."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO focus_sessions (todo_id, timer_preset)
            VALUES (?, ?)
            """,
            (todo_id, timer_preset),
        )
        session_id = cur.lastrowid
        conn.execute(
            "UPDATE todos SET status = 'active' WHERE id = ?", (todo_id,)
        )
    return session_get(db_path, session_id)  # type: ignore[return-value]

def session_end(
    db_path: Path,
    session_id: int,
    outcome: Outcome,
    log_entry: str = "",
) -> FocusSession:
    """
    Session beenden:
    - duration_s berechnen
    - Todo-Status je nach Outcome setzen
    - Optionalen Log-Eintrag zurückgeben (wird vom Caller ins log_entries geschrieben)
    """
    ended_at = _now()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT todo_id, started_at FROM focus_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Session {session_id} nicht gefunden")

        started = datetime.fromisoformat(row["started_at"])
        ended   = datetime.fromisoformat(ended_at)
        duration_s = int((ended - started).total_seconds())

        conn.execute(
            """
            UPDATE focus_sessions
            SET ended_at = ?, duration_s = ?, outcome = ?, log_entry = ?
            WHERE id = ?
            """,
            (ended_at, duration_s, outcome, log_entry.strip(), session_id),
        )

        new_status: Status = (
            "done" if outcome == "solved"
            else "paused" if outcome == "open"
            else "paused"   # blocked → paused, User kann manuell auf 'blocked' setzen
        )
        done_at = ended_at if outcome == "solved" else None
        conn.execute(
            "UPDATE todos SET status = ?, done_at = ? WHERE id = ?",
            (new_status, done_at, row["todo_id"]),
        )

    return session_get(db_path, session_id)  # type: ignore[arg-type]

def session_get(db_path: Path, session_id: int) -> FocusSession | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return _row_to_session(row) if row else None

def session_get_active(db_path: Path) -> FocusSession | None:
    """Laufende Session (ended_at IS NULL). Max. eine gleichzeitig."""
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    return _row_to_session(row) if row else None

def session_list_for_todo(db_path: Path, todo_id: int) -> list[FocusSession]:
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM focus_sessions WHERE todo_id = ? ORDER BY started_at",
            (todo_id,),
        ).fetchall()
    return [_row_to_session(r) for r in rows]

def session_total_today(db_path: Path) -> int:
    """Gesamte Focus-Zeit heute in Sekunden."""
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(duration_s), 0)
            FROM focus_sessions
            WHERE date(started_at) = date('now', 'localtime')
              AND ended_at IS NOT NULL
            """
        ).fetchone()
    return row[0] if row else 0

# ─────────────────────────────────────────────────────────────────────────────
# TODO NOTES
# ─────────────────────────────────────────────────────────────────────────────

def note_add(
    db_path: Path,
    todo_id: int,
    content: str,
    session_id: int | None = None,
) -> TodoNote:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO todo_notes (todo_id, session_id, content)
            VALUES (?, ?, ?)
            """,
            (todo_id, session_id, content.strip()),
        )
        note_id = cur.lastrowid
    return note_get(db_path, note_id)  # type: ignore[return-value]

def note_get(db_path: Path, note_id: int) -> TodoNote | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM todo_notes WHERE id = ?", (note_id,)
        ).fetchone()
    return _row_to_note(row) if row else None

def note_list_for_todo(db_path: Path, todo_id: int) -> list[TodoNote]:
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM todo_notes WHERE todo_id = ? ORDER BY created_at",
            (todo_id,),
        ).fetchall()
    return [_row_to_note(r) for r in rows]

def note_list_for_session(db_path: Path, session_id: int) -> list[TodoNote]:
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM todo_notes WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [_row_to_note(r) for r in rows]

def note_delete(db_path: Path, note_id: int) -> bool:
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM todo_notes WHERE id = ?", (note_id,))
    return cur.rowcount > 0

# ─────────────────────────────────────────────────────────────────────────────
# SUB-TODOS
# ─────────────────────────────────────────────────────────────────────────────

def subtodo_add(db_path: Path, todo_id: int, title: str) -> SubTodo:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO sub_todos (todo_id, title) VALUES (?, ?)",
            (todo_id, title.strip()),
        )
        subtodo_id = cur.lastrowid
    return subtodo_get(db_path, subtodo_id)  # type: ignore[return-value]

def subtodo_get(db_path: Path, subtodo_id: int) -> SubTodo | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM sub_todos WHERE id = ?", (subtodo_id,)
        ).fetchone()
    return _row_to_subtodo(row) if row else None

def subtodo_list_for_todo(db_path: Path, todo_id: int) -> list[SubTodo]:
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(
            "SELECT * FROM sub_todos WHERE todo_id = ? ORDER BY created_at",
            (todo_id,),
        ).fetchall()
    return [_row_to_subtodo(r) for r in rows]

def subtodo_toggle(db_path: Path, subtodo_id: int) -> SubTodo | None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE sub_todos SET done = NOT done WHERE id = ?",
            (subtodo_id,),
        )
    return subtodo_get(db_path, subtodo_id)

def subtodo_delete(db_path: Path, subtodo_id: int) -> bool:
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM sub_todos WHERE id = ?", (subtodo_id,))
    return cur.rowcount > 0

# ─────────────────────────────────────────────────────────────────────────────
# PROJECTS
# ─────────────────────────────────────────────────────────────────────────────

def project_add(
    db_path: Path,
    name: str,
    tag_key: str | None = None,
    phase: Phase = "active",
) -> Project:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, tag_key, phase) VALUES (?, ?, ?)",
            (name.strip(), tag_key, phase),
        )
        project_id = cur.lastrowid
    return project_get(db_path, project_id)  # type: ignore[return-value]

def project_get(db_path: Path, project_id: int) -> Project | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    return _row_to_project(row) if row else None

def project_get_by_name(db_path: Path, name: str) -> Project | None:
    with get_connection(db_path, readonly=True) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
    return _row_to_project(row) if row else None

def project_list(db_path: Path, phase: Phase | None = None) -> list[Project]:
    sql = "SELECT * FROM projects"
    params: list = []
    if phase:
        sql += " WHERE phase = ?"
        params.append(phase)
    sql += " ORDER BY created_at"
    with get_connection(db_path, readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_project(r) for r in rows]

def project_set_phase(db_path: Path, project_id: int, phase: Phase) -> Project | None:
    done_at = _now() if phase == "done" else None
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE projects SET phase = ?, done_at = ? WHERE id = ?",
            (phase, done_at, project_id),
        )
    return project_get(db_path, project_id)

def project_upsert_from_config(db_path: Path, names: list[str]) -> None:
    """
    Projekte aus config.toml in die DB synchronisieren.
    Neue werden angelegt, bestehende bleiben unverändert.
    """
    with get_connection(db_path) as conn:
        for name in names:
            conn.execute(
                "INSERT OR IGNORE INTO projects (name, phase) VALUES (?, 'active')",
                (name,),
            )

# ─────────────────────────────────────────────────────────────────────────────
# WOCHENRÜCKBLICK
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WeekSummary:
    iso_week: str                   # "2026-W14"
    work_days: int
    log_counts: dict[str, int]      # {"done": 5, "block": 2, ...}
    avg_energy: float | None
    top_tags: list[tuple[str, int]] # [("done", 5), ("idea", 3)]
    open_blocks: int
    focus_total_s: int              # Gesamte Focus-Zeit der Woche
    day_ratings: list[str]

def _iso_week_to_date_range(iso_week: str) -> tuple[str, str]:
    """
    "2026-W14"  →  ("2026-03-30", "2026-04-05")
    Montag bis Sonntag der ISO-Woche.
    """
    from datetime import date, timedelta
    year, week = iso_week.split("-W")
    # ISO-Woche: Montag ist Tag 1
    monday = date.fromisocalendar(int(year), int(week), 1)
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()

def week_summary(db_path: Path, iso_week: str) -> WeekSummary:
    """
    Aggregierte Wochenstatistik.
    iso_week: "2026-W14"
    """
    date_from, date_to = _iso_week_to_date_range(iso_week)

    with get_connection(db_path, readonly=True) as conn:

        log_rows = conn.execute(
            """
            SELECT tag_key, COUNT(*) as cnt
            FROM log_entries
            WHERE date BETWEEN ? AND ?
            GROUP BY tag_key
            ORDER BY cnt DESC
            """,
            (date_from, date_to),
        ).fetchall()

        day_rows = conn.execute(
            """
            SELECT morning_energy, day_rating, mode
            FROM day_meta
            WHERE date BETWEEN ? AND ?
            """,
            (date_from, date_to),
        ).fetchall()

        focus_row = conn.execute(
            """
            SELECT COALESCE(SUM(duration_s), 0)
            FROM focus_sessions
            WHERE date(started_at) BETWEEN ? AND ?
              AND ended_at IS NOT NULL
            """,
            (date_from, date_to),
        ).fetchone()

        open_blocks_row = conn.execute(
            """
            SELECT COUNT(*)
            FROM log_entries
            WHERE date BETWEEN ? AND ?
              AND tag_key = 'block'
            """,
            (date_from, date_to),
        ).fetchone()

    log_counts  = {r["tag_key"]: r["cnt"] for r in log_rows}
    top_tags    = [(r["tag_key"], r["cnt"]) for r in log_rows[:5]]
    energies    = [r["morning_energy"] for r in day_rows if r["morning_energy"]]
    avg_energy  = sum(energies) / len(energies) if energies else None
    work_days   = sum(1 for r in day_rows if r["mode"] == "work")
    ratings     = [r["day_rating"] for r in day_rows if r["day_rating"]]

    return WeekSummary(
        iso_week=iso_week,
        work_days=work_days,
        log_counts=log_counts,
        avg_energy=avg_energy,
        top_tags=top_tags,
        open_blocks=open_blocks_row[0] if open_blocks_row else 0,
        focus_total_s=focus_row[0] if focus_row else 0,
        day_ratings=ratings,
    )
