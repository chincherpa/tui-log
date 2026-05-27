"""Application state for the Flet UI.

Holds loaded entities (log entries, todos, active session, filter, selection)
and exposes load/refresh methods. UI code subscribes via the `on_change`
callback set by `flet_app.main`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from tui_log import db_utils as db
from tui_log.tags import TagRegistry

class AppState:
    def __init__(self, db_path: Path, tags: TagRegistry, work_tags: list) -> None:
        self.db_path = db_path
        self.tags = tags
        self.work_tags = work_tags

        self.log_entries: list[db.LogEntry] = []
        self.todos: list[db.Todo] = []
        self.carry_over: list[db.LogEntry] = []
        self.active_session: db.FocusSession | None = None
        self.active_session_title: str = ""
        self.active_session_base_s: int = 0

        self.tag_idx: int = 0
        self.todo_idx: int = 0
        self.log_filter: str | None = None
        self.filter_keys: list[str | None] = [None]
        self.displayed_entry_id: int | None = None

        self.on_change: Callable[[], None] | None = None

    # ── load helpers ──────────────────────────────────────────────────────

    def load_all(self) -> None:
        self.load_log()
        self.load_todos()
        self.load_carry_over()
        self.check_active_session()

    def load_log(self) -> None:
        self.log_entries = db.log_get_all(self.db_path, mode="work")
        # log_used_tags returns set[str] (tag key strings, not Tag objects)
        used = db.log_used_tags(self.db_path, mode="work")
        self.filter_keys = [None] + [t.key for t in self.work_tags if t.key in used]
        if self.log_filter not in self.filter_keys:
            self.log_filter = None
        if not self.log_entries:
            self.displayed_entry_id = None
            return
        filtered = self._filtered_entries()
        existing_ids = {e.id for e in filtered}
        if self.displayed_entry_id in existing_ids:
            return
        self.displayed_entry_id = filtered[0].id if filtered else None

    def select_entry_relative(self, direction: int) -> None:
        entries = self._filtered_entries()
        if not entries:
            return
        ids = [e.id for e in entries]
        if self.displayed_entry_id in ids:
            idx = ids.index(self.displayed_entry_id) + direction
        else:
            idx = 0
        idx = max(0, min(idx, len(ids) - 1))
        self.displayed_entry_id = ids[idx]

    def load_todos(self) -> None:
        current_id = self.todos[self.todo_idx].id if self.todos else None
        self.todos = db.todo_list(self.db_path, mode="work")
        self.todos.sort(key=lambda t: (
            0 if t.status == "active"
            else 1 if t.status in ("open", "paused")
            else 2 if t.status == "done"
            else 3,  # cancelled/dropped at very bottom
            t.created_at,
        ))
        if current_id is not None:
            ids = [t.id for t in self.todos]
            self.todo_idx = ids.index(current_id) if current_id in ids else 0
        self.clamp_todo_idx()

    def load_carry_over(self) -> None:
        today = date.today().isoformat()
        self.carry_over = db.log_get_open_blocks(self.db_path, before_date=today)

    def check_active_session(self) -> None:
        sess = db.session_get_active(self.db_path)
        self.active_session = sess
        if sess:
            todo = db.todo_get(self.db_path, sess.todo_id)
            self.active_session_title = todo.title[:30] if todo else "?"
            self.active_session_base_s = int(todo.total_duration_s) if todo else 0
        else:
            self.active_session_title = ""
            self.active_session_base_s = 0

    # ── selectors / mutators ──────────────────────────────────────────────

    def clamp_todo_idx(self) -> None:
        if not self.todos:
            self.todo_idx = 0
        else:
            self.todo_idx = max(0, min(self.todo_idx, len(self.todos) - 1))

    def _filtered_entries(self) -> list[db.LogEntry]:
        if self.log_filter is None:
            return self.log_entries
        return [e for e in self.log_entries if e.tag_key == self.log_filter]

    def filtered_entries(self) -> list[db.LogEntry]:
        return self._filtered_entries()

    def cycle_filter(self, direction: int) -> None:
        if not self.filter_keys:
            return
        idx = self.filter_keys.index(self.log_filter) if self.log_filter in self.filter_keys else 0
        self.log_filter = self.filter_keys[(idx + direction) % len(self.filter_keys)]

    def cycle_tag(self, direction: int) -> None:
        if self.work_tags:
            self.tag_idx = (self.tag_idx + direction) % len(self.work_tags)

    def notify(self) -> None:
        if self.on_change:
            self.on_change()
