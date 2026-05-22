# Flet-Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing Textual TUI work-journal to a standalone Windows desktop app using Flet, replacing the terminal UI entirely while keeping the SQLite backend and `journal.db` schema unchanged.

**Architecture:** Backend modules under `tui_log/` (`db_utils`, `config`, `tags`, `mode`, `schema`) are reused as-is. New `flet_app/` package contains all UI code. Single-window, three-column layout (log / content / todo) with dialog overlays for modals (focus, debriefing, new-todo, weekly review, tag-select, content-edit). Live state held in an `AppState` class that wraps DB calls and triggers `page.update()`. Keybindings handled via `page.on_keyboard_event` with context-aware Tab / Shift+Tab logic.

**Tech Stack:** Python 3.11+, Flet ≥ 0.25.0 (Flutter renderer), existing SQLite + stdlib backend, `flet build windows` for `.exe` packaging.

---

## File Structure

**New files:**
- `flet_app/__init__.py` — package marker
- `flet_app/main.py` — entry point: `ft.app(target=main)`, page setup, dark theme
- `flet_app/state.py` — `AppState` class wrapping DB calls and reactive UI refresh
- `flet_app/theme.py` — color constants (mirrors current `STATUS_COLORS`, `PRIORITY_COLORS`, tag colors)
- `flet_app/keybindings.py` — central key dispatch with panel-cycle / context-aware Tab logic
- `flet_app/panels/__init__.py`
- `flet_app/panels/log_panel.py` — left column: filter bar, carry-over, log list, tag-prefixed input row
- `flet_app/panels/content_panel.py` — middle column: read-only markdown view of selected log entry
- `flet_app/panels/todo_panel.py` — right column: active-session bar, todo list with selection
- `flet_app/dialogs/__init__.py`
- `flet_app/dialogs/focus.py` — focus session dialog with live timer
- `flet_app/dialogs/debriefing.py` — outcome + log-entry capture
- `flet_app/dialogs/new_todo.py` — title / context / priority form
- `flet_app/dialogs/weekly.py` — weekly review overlay
- `flet_app/dialogs/tag_select.py` — tag picker for log-entry edits
- `flet_app/dialogs/content_edit.py` — multi-line text editor for log entries
- `flet_app/dialogs/confirm.py` — generic Ja/Nein confirm dialog
- `flet_app/git_push.py` — async git add/commit/push of `journal.db` with toast feedback
- `flet_app/widgets/log_entry_row.py` — single log entry row widget
- `flet_app/widgets/todo_row.py` — single todo row widget (two lines, status icon, stats)
- `flet_app/widgets/toast.py` — `ft.SnackBar` helper for transient feedback
- `tests/test_state.py` — unit tests for `AppState` (DB roundtrip, filter, sort, selection)

**Modified files:**
- `pyproject.toml` (or new if missing) — add `flet>=0.25.0` dependency, `flet build` config
- `work_app.py` (root shim) — keep `--config` arg parsing; switch import to `flet_app.main:run`
- `tui_log/__main__.py` — replace `WorkApp(cfg).run()` with `flet_app.main.run(cfg)`
- `CLAUDE.md` — update Architecture section, command list, layout diagram
- `.gitignore` — add `build/`, `dist/`, `*.spec`

**Deleted (after parity verified, last task):**
- `tui_log/work_app.py`
- `tui_log/work.tcss`
- `tui_log/widgets/` (entire dir: `focus.py`, `debriefing.py`, `new_todo.py`, `log_input.py`, `content_view.py`)
- `tui_log/views/` (entire dir: `weekly.py`)

---

## Task 1: Add Flet dependency and project config

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Create `pyproject.toml` with Flet dependency**

```toml
[project]
name = "tui-log"
version = "0.2.0"
description = "Daily work journal — Flet desktop app"
requires-python = ">=3.11"
dependencies = [
    "flet>=0.25.0",
]

[tool.flet]
org = "local"
product = "tui-log"
company = "private"
copyright = "Copyright (c) 2026"

[tool.flet.app]
path = "flet_app"
```

- [ ] **Step 2: Add build artifacts to `.gitignore`**

Append these lines to `.gitignore` (create file if it does not exist):

```
build/
dist/
*.spec
__pycache__/
*.pyc
```

- [ ] **Step 3: Install Flet locally**

Run: `pip install flet>=0.25.0`
Expected: `Successfully installed flet-0.25.x ...`

- [ ] **Step 4: Verify Flet import works**

Run: `python -c "import flet as ft; print(ft.__version__)"`
Expected: prints version string `0.25.x` or higher; no traceback.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: add flet dependency and project config"
```

---

## Task 2: Create theme constants

**Files:**
- Create: `flet_app/__init__.py`
- Create: `flet_app/theme.py`

- [ ] **Step 1: Create empty package marker**

Create `flet_app/__init__.py` with content:

```python
"""Flet desktop app for tui-log."""
```

- [ ] **Step 2: Create `flet_app/theme.py`**

```python
"""Color and style constants — mirrors the dark theme of the original Textual app."""

from __future__ import annotations

# ── Background / surface ──────────────────────────────────────────────────
BG_BASE      = "#0E1117"
BG_PANEL     = "#11151C"
BG_SELECTED  = "#1E2530"
BORDER       = "#2A3340"
BORDER_ACTIVE = "#5B8DEF"

# ── Text ──────────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#E8E8E8"
TEXT_SECONDARY = "#888899"
TEXT_DIM       = "#555577"

# ── Status (todo) ─────────────────────────────────────────────────────────
STATUS_COLORS = {
    "open":      "#C8C8C8",
    "active":    "#66FF66",
    "paused":    "#FFD700",
    "done":      "#2E7D32",
    "dropped":   "#8B0000",
    "cancelled": "#8B0000",
    "focus":     "#55CCFF",
}

STATUS_ICONS = {
    "open":      "○",
    "active":    "▶",
    "paused":    "‖",
    "done":      "✓",
    "dropped":   "✗",
    "cancelled": "✗",
    "focus":     "◉",
}

# ── Priority ──────────────────────────────────────────────────────────────
PRIORITY_COLORS = {
    "high":   "#FF6B6B",
    "normal": "#C8C8C8",
    "low":    "#555577",
}

# ── Accent ────────────────────────────────────────────────────────────────
ACCENT_BLUE = "#5B8DEF"
ACCENT_RED  = "#FF6B6B"
ACCENT_GOLD = "#FFD700"
```

- [ ] **Step 3: Verify import**

Run: `python -c "from flet_app import theme; print(theme.STATUS_COLORS['active'])"`
Expected: `#66FF66`

- [ ] **Step 4: Commit**

```bash
git add flet_app/__init__.py flet_app/theme.py
git commit -m "feat(flet): add theme constants"
```

---

## Task 3: AppState skeleton with TDD

**Files:**
- Create: `flet_app/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests for `AppState`**

Create `tests/test_state.py`:

```python
"""Tests for flet_app.state.AppState — uses temp DB."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make repo importable when run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tui_log.schema import init_db
from tui_log import db_utils as db
from tui_log.tags import TagRegistry
from flet_app.state import AppState


def _make_state(tmp: Path) -> AppState:
    db_path = tmp / "journal.db"
    init_db(db_path)
    # Minimal in-memory tag registry: the production code reads from config.toml
    # but for state tests we only need keys that match what we insert.
    tags = TagRegistry.__new__(TagRegistry)
    tags._tags = {}  # not used by state
    state = AppState(db_path=db_path, tags=tags, work_tags=[])
    state.load_all()
    return state


class TestAppState(unittest.TestCase):

    def test_load_all_empty_db(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            self.assertEqual(s.log_entries, [])
            self.assertEqual(s.todos, [])
            self.assertIsNone(s.active_session)

    def test_log_entries_loaded_after_insert(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            db.log_add(s.db_path, tag_key="info", content="hello", mode="work")
            s.load_log()
            self.assertEqual(len(s.log_entries), 1)
            self.assertEqual(s.log_entries[0].content, "hello")

    def test_todo_selected_index_clamps(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            db.todo_add(s.db_path, title="A", context=None, priority="normal", mode="work")
            db.todo_add(s.db_path, title="B", context=None, priority="normal", mode="work")
            s.load_todos()
            s.todo_idx = 99
            s.clamp_todo_idx()
            self.assertEqual(s.todo_idx, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/test_state.py`
Expected: ImportError on `from flet_app.state import AppState`.

- [ ] **Step 3: Implement minimal `AppState`**

Create `flet_app/state.py`:

```python
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
        used = db.log_used_tags(self.db_path, mode="work")
        self.filter_keys = [None] + [t.key for t in self.work_tags if t.key in used]
        if self.log_filter not in self.filter_keys:
            self.log_filter = None
        if self.log_entries:
            self.displayed_entry_id = self._filtered_entries()[0].id if self._filtered_entries() else None
        else:
            self.displayed_entry_id = None

    def load_todos(self) -> None:
        current_id = self.todos[self.todo_idx].id if self.todos else None
        self.todos = db.todo_list(self.db_path, mode="work")
        self.todos.sort(key=lambda t: (
            0 if t.status == "active"
            else 1 if t.status in ("open", "paused")
            else 2 if t.status == "done"
            else 3,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python tests/test_state.py`
Expected: `OK` — all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add flet_app/state.py tests/test_state.py
git commit -m "feat(flet): add AppState with load/select/filter logic"
```

---

## Task 4: Toast helper

**Files:**
- Create: `flet_app/widgets/__init__.py`
- Create: `flet_app/widgets/toast.py`

- [ ] **Step 1: Create widgets package marker**

Create `flet_app/widgets/__init__.py` with content:

```python
"""Reusable Flet UI widgets for tui-log."""
```

- [ ] **Step 2: Create toast helper**

Create `flet_app/widgets/toast.py`:

```python
"""Transient feedback via Flet SnackBar."""

from __future__ import annotations

import flet as ft

from flet_app import theme


def show_toast(page: ft.Page, message: str, *, severity: str = "info", duration_ms: int = 2000) -> None:
    """Display a transient SnackBar at the bottom of the page."""
    bg = {
        "info":    theme.BG_PANEL,
        "warning": theme.ACCENT_GOLD,
        "error":   theme.ACCENT_RED,
        "success": theme.STATUS_COLORS["active"],
    }.get(severity, theme.BG_PANEL)
    fg = "#000000" if severity in ("warning", "success") else theme.TEXT_PRIMARY

    snack = ft.SnackBar(
        content=ft.Text(message, color=fg),
        bgcolor=bg,
        duration=duration_ms,
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()
```

- [ ] **Step 3: Verify import**

Run: `python -c "from flet_app.widgets.toast import show_toast; print(show_toast)"`
Expected: prints `<function show_toast at 0x...>`.

- [ ] **Step 4: Commit**

```bash
git add flet_app/widgets/__init__.py flet_app/widgets/toast.py
git commit -m "feat(flet): add toast helper"
```

---

## Task 5: Log entry row widget

**Files:**
- Create: `flet_app/widgets/log_entry_row.py`

- [ ] **Step 1: Implement log entry row**

Create `flet_app/widgets/log_entry_row.py`:

```python
"""Single log entry row — displays time, tag chip, first line, body indicator."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db
from tui_log.tags import TagRegistry

from flet_app import theme


def _fmt_time(iso_dt: str) -> str:
    try:
        return iso_dt[11:16]
    except (TypeError, IndexError):
        return "??:??"


def build_log_entry_row(
    entry: db.LogEntry,
    tags: TagRegistry,
    *,
    selected: bool,
    on_click: Callable[[db.LogEntry], None],
) -> ft.Control:
    tag = tags.get(entry.tag_key)
    symbol = tag.symbol if tag else "·"
    color  = tag.color  if tag else theme.TEXT_SECONDARY
    time_s = _fmt_time(entry.created_at)
    first_line = entry.content.split("\n", 1)[0]
    has_body = "\n" in entry.content and entry.content.split("\n", 1)[1].strip()

    row = ft.Row(
        [
            ft.Text(time_s, color=theme.TEXT_DIM, size=12, width=44),
            ft.Container(
                content=ft.Text(f"{symbol} {entry.tag_key}", color=color, weight="bold", size=12),
                width=80,
            ),
            ft.Text(
                ("📄 " if has_body else "") + first_line,
                color=theme.TEXT_PRIMARY,
                size=13,
                expand=True,
                overflow="ellipsis",
                max_lines=1,
            ),
        ],
        spacing=8,
        vertical_alignment="center",
    )

    return ft.Container(
        content=row,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        bgcolor=theme.BG_SELECTED if selected else None,
        border_radius=4,
        on_click=lambda _e: on_click(entry),
    )


def build_date_separator(label: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(f"── {label} ──", color=theme.TEXT_DIM, size=11),
        padding=ft.padding.symmetric(horizontal=8, vertical=2),
    )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.widgets.log_entry_row import build_log_entry_row; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/widgets/log_entry_row.py
git commit -m "feat(flet): add log entry row widget"
```

---

## Task 6: Todo row widget

**Files:**
- Create: `flet_app/widgets/todo_row.py`

- [ ] **Step 1: Implement todo row**

Create `flet_app/widgets/todo_row.py`:

```python
"""Two-line todo row: status icon, title, context, stats."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    h = m // 60
    if h == 0:
        return f"{m}m"
    return f"{h}h{m % 60:02d}"


def build_todo_row(
    todo: db.Todo,
    *,
    selected: bool,
    is_focus: bool,
    on_click: Callable[[db.Todo], None],
) -> ft.Control:
    effective_status = "focus" if is_focus else todo.status
    icon = theme.STATUS_ICONS.get(effective_status, "○")
    color = theme.STATUS_COLORS.get(effective_status, theme.TEXT_PRIMARY)

    ctx = (todo.context or "")[:32]
    dur = _fmt_duration(todo.total_duration_s) if todo.total_duration_s else ""
    sess = f"{todo.total_sessions}×" if todo.total_sessions else ""
    stats = f"{sess} {dur}".strip()

    line1 = ft.Row(
        [
            ft.Text(icon, color=color, size=14, width=20),
            ft.Text(todo.title, color=color, weight="bold", size=13, expand=True, overflow="ellipsis", max_lines=1),
        ],
        spacing=4,
        vertical_alignment="center",
    )

    line2_children = []
    if ctx:
        line2_children.append(ft.Text(ctx, color=theme.TEXT_DIM, size=11))
    if stats:
        line2_children.append(ft.Text(stats, color=theme.TEXT_DIM, size=11))
    line2 = ft.Row(line2_children, spacing=8) if line2_children else ft.Container(height=0)

    return ft.Container(
        content=ft.Column([line1, line2], spacing=2),
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        bgcolor=theme.BG_SELECTED if selected else None,
        border=ft.border.only(left=ft.BorderSide(3, theme.ACCENT_BLUE)) if selected else None,
        border_radius=4,
        on_click=lambda _e: on_click(todo),
    )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.widgets.todo_row import build_todo_row; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/widgets/todo_row.py
git commit -m "feat(flet): add todo row widget"
```

---

## Task 7: Log panel

**Files:**
- Create: `flet_app/panels/__init__.py`
- Create: `flet_app/panels/log_panel.py`

- [ ] **Step 1: Create panels package marker**

Create `flet_app/panels/__init__.py` with content:

```python
"""Three-column panel layout for the Flet UI."""
```

- [ ] **Step 2: Implement log panel**

Create `flet_app/panels/log_panel.py`:

```python
"""Left column: filter bar, carry-over warning, log list, tag-prefixed input row."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme
from flet_app.state import AppState
from flet_app.widgets.log_entry_row import build_log_entry_row, build_date_separator


class LogPanel(ft.Container):
    """Left column container — full panel widget."""

    def __init__(
        self,
        state: AppState,
        on_entry_select: Callable[[db.LogEntry], None],
        on_log_submit: Callable[[str], None],
        on_input_focus_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.state = state
        self.on_entry_select = on_entry_select
        self.on_log_submit = on_log_submit
        self.on_input_focus_change = on_input_focus_change

        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.filter_bar = ft.Row([], spacing=8, wrap=True)
        self.carry_over = ft.Text("", color=theme.ACCENT_GOLD, size=11, visible=False)
        self.list_view = ft.ListView(spacing=2, padding=4, expand=True, auto_scroll=False)

        self.tag_chip = ft.Container(
            content=ft.Text("", color=theme.TEXT_PRIMARY, size=12, weight="bold"),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.BG_PANEL,
            border_radius=4,
        )
        self.input = ft.TextField(
            hint_text="Eintrag… (Shift+Tab = Tag wechseln)",
            border_color=theme.BORDER,
            focused_border_color=theme.ACCENT_BLUE,
            text_size=13,
            content_padding=8,
            expand=True,
            on_submit=self._handle_submit,
            on_focus=lambda _e: self.on_input_focus_change and self.on_input_focus_change(True),
            on_blur=lambda _e: self.on_input_focus_change and self.on_input_focus_change(False),
        )
        input_row = ft.Row([self.tag_chip, self.input], spacing=6)

        super().__init__(
            content=ft.Column(
                [self.title, self.filter_bar, self.carry_over, self.list_view, input_row],
                spacing=6,
                expand=True,
            ),
            padding=8,
            bgcolor=theme.BG_PANEL,
            border=ft.border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def focus_input(self) -> None:
        self.input.focus()

    def render(self) -> None:
        self._render_title()
        self._render_filter_bar()
        self._render_carry_over()
        self._render_list()
        self._render_tag_chip()
        self.update()

    def _render_title(self) -> None:
        now = datetime.now()
        today = date.today().isoformat()
        today_count = sum(1 for e in self.state.log_entries if e.date == today)
        self.title.value = f"  📋 LOG  ·  {now.strftime('%a, %d. %b')}  ·  {today_count} Einträge heute"

    def _render_filter_bar(self) -> None:
        chips: list[ft.Control] = []
        for key in self.state.filter_keys:
            if key is None:
                label, color = "Alle", theme.ACCENT_BLUE
            else:
                tag = self.state.tags.get(key)
                label = f"{tag.symbol} {tag.key}" if tag else key
                color = tag.color if tag else theme.TEXT_SECONDARY
            active = self.state.log_filter == key
            chips.append(
                ft.Container(
                    content=ft.Text(label, color="#000000" if active else color, size=11, weight="bold"),
                    bgcolor=color if active else None,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    border_radius=10,
                )
            )
        self.filter_bar.controls = chips

    def _render_carry_over(self) -> None:
        if self.state.carry_over:
            items = [e.content[:48] for e in self.state.carry_over[:3]]
            self.carry_over.value = "  ↩  " + "  ·  ".join(items)
            self.carry_over.visible = True
        else:
            self.carry_over.visible = False

    def _render_list(self) -> None:
        entries = self.state.filtered_entries()
        self.list_view.controls.clear()
        if not entries:
            self.list_view.controls.append(
                ft.Text("  (noch keine Einträge)", color=theme.TEXT_DIM, italic=True)
            )
            return
        today = date.today().isoformat()
        current_date = None
        for e in entries:
            if e.date != current_date:
                current_date = e.date
                if e.date == today:
                    label = "Heute"
                else:
                    try:
                        label = date.fromisoformat(e.date).strftime("%a, %d. %b %Y")
                    except ValueError:
                        label = e.date
                self.list_view.controls.append(build_date_separator(label))
            selected = (e.id == self.state.displayed_entry_id)
            self.list_view.controls.append(
                build_log_entry_row(e, self.state.tags, selected=selected, on_click=self._handle_click)
            )

    def _render_tag_chip(self) -> None:
        if not self.state.work_tags:
            return
        tag = self.state.work_tags[self.state.tag_idx]
        self.tag_chip.content = ft.Text(
            f"{tag.symbol} {tag.key}", color=tag.color, size=12, weight="bold"
        )

    def _handle_click(self, entry: db.LogEntry) -> None:
        self.on_entry_select(entry)

    def _handle_submit(self, _e: ft.ControlEvent) -> None:
        text = self.input.value.strip() if self.input.value else ""
        if not text:
            return
        self.input.value = ""
        self.on_log_submit(text)
```

- [ ] **Step 3: Verify import**

Run: `python -c "from flet_app.panels.log_panel import LogPanel; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add flet_app/panels/__init__.py flet_app/panels/log_panel.py
git commit -m "feat(flet): add log panel"
```

---

## Task 8: Content panel

**Files:**
- Create: `flet_app/panels/content_panel.py`

- [ ] **Step 1: Implement content panel**

Create `flet_app/panels/content_panel.py`:

```python
"""Middle column: read-only display of the currently selected log entry."""

from __future__ import annotations

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


class ContentPanel(ft.Container):
    def __init__(self) -> None:
        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.body = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            code_theme="atom-one-dark",
        )
        self.scroll = ft.Column([self.body], scroll="auto", expand=True)
        super().__init__(
            content=ft.Column([self.title, self.scroll], spacing=6, expand=True),
            padding=12,
            bgcolor=theme.BG_PANEL,
            border=ft.border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def show_entry(self, entry: db.LogEntry | None) -> None:
        if entry is None:
            self.title.value = "  📄 CONTENT"
            self.body.value = "_(kein Eintrag ausgewählt)_"
        else:
            self.title.value = f"  📄 {entry.tag_key.upper()}  ·  {entry.created_at[:16]}"
            parts = entry.content.split("\n", 1)
            head = f"### {parts[0]}\n"
            tail = parts[1] if len(parts) > 1 else ""
            self.body.value = head + ("\n---\n\n" + tail if tail.strip() else "")
        self.update()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.panels.content_panel import ContentPanel; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/panels/content_panel.py
git commit -m "feat(flet): add content panel"
```

---

## Task 9: Todo panel

**Files:**
- Create: `flet_app/panels/todo_panel.py`

- [ ] **Step 1: Implement todo panel**

Create `flet_app/panels/todo_panel.py`:

```python
"""Right column: active session bar + todo list."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme
from flet_app.state import AppState
from flet_app.widgets.todo_row import build_todo_row


class TodoPanel(ft.Container):
    def __init__(self, state: AppState, on_todo_select: Callable[[db.Todo], None]) -> None:
        self.state = state
        self.on_todo_select = on_todo_select

        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.session_bar = ft.Container(
            content=ft.Text("", color=theme.STATUS_COLORS["active"], size=12, weight="bold"),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.BG_SELECTED,
            border_radius=4,
            visible=False,
        )
        self.list_view = ft.ListView(spacing=4, padding=4, expand=True)

        super().__init__(
            content=ft.Column([self.title, self.session_bar, self.list_view], spacing=6, expand=True),
            padding=8,
            bgcolor=theme.BG_PANEL,
            border=ft.border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def render(self) -> None:
        self._render_title()
        self._render_list()
        self.update()

    def update_session_timer(self, label: str | None) -> None:
        if label is None:
            self.session_bar.visible = False
        else:
            self.session_bar.visible = True
            self.session_bar.content = ft.Text(label, color=theme.STATUS_COLORS["active"], size=12, weight="bold")
        self.session_bar.update()

    def _render_title(self) -> None:
        active_cnt = sum(1 for t in self.state.todos if t.status in ("open", "active", "paused"))
        done_cnt   = sum(1 for t in self.state.todos if t.status == "done")
        self.title.value = f"  ✅ TODOS  ·  {active_cnt} offen  ·  {done_cnt} done"

    def _render_list(self) -> None:
        self.list_view.controls.clear()
        if not self.state.todos:
            self.list_view.controls.append(
                ft.Text("  (keine Todos – [a] um eines anzulegen)", color=theme.TEXT_DIM, italic=True)
            )
            return
        focus_id = self.state.active_session.todo_id if self.state.active_session else None
        for i, todo in enumerate(self.state.todos):
            self.list_view.controls.append(
                build_todo_row(
                    todo,
                    selected=(i == self.state.todo_idx),
                    is_focus=(todo.id == focus_id),
                    on_click=self.on_todo_select,
                )
            )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.panels.todo_panel import TodoPanel; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/panels/todo_panel.py
git commit -m "feat(flet): add todo panel"
```

---

## Task 10: Confirm dialog

**Files:**
- Create: `flet_app/dialogs/__init__.py`
- Create: `flet_app/dialogs/confirm.py`

- [ ] **Step 1: Create dialogs package marker**

Create `flet_app/dialogs/__init__.py` with content:

```python
"""Modal dialogs for the Flet UI."""
```

- [ ] **Step 2: Implement confirm dialog**

Create `flet_app/dialogs/confirm.py`:

```python
"""Generic Ja/Nein confirmation dialog."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme


def show_confirm(page: ft.Page, message: str, on_confirm: Callable[[bool], None]) -> None:
    def _close(result: bool) -> None:
        page.close(dlg)
        on_confirm(result)

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text(message, color=theme.TEXT_PRIMARY, size=14),
        actions=[
            ft.TextButton("Nein", on_click=lambda _e: _close(False)),
            ft.FilledButton("Ja", on_click=lambda _e: _close(True),
                            style=ft.ButtonStyle(bgcolor=theme.ACCENT_RED, color="#FFFFFF")),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
```

- [ ] **Step 3: Verify import**

Run: `python -c "from flet_app.dialogs.confirm import show_confirm; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add flet_app/dialogs/__init__.py flet_app/dialogs/confirm.py
git commit -m "feat(flet): add confirm dialog"
```

---

## Task 11: New-todo dialog

**Files:**
- Create: `flet_app/dialogs/new_todo.py`

- [ ] **Step 1: Implement new todo dialog**

Create `flet_app/dialogs/new_todo.py`:

```python
"""Dialog to create a new todo (title, context, priority)."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme

PRIORITIES = ["high", "normal", "low"]
PRIORITY_DISPLAY = {"high": "▲ high", "normal": "● normal", "low": "▼ low"}


def show_new_todo(
    page: ft.Page,
    on_save: Callable[[dict | None], None],
    *,
    prefill_title: str = "",
) -> None:
    title_input = ft.TextField(label="Titel", value=prefill_title, autofocus=True,
                               border_color=theme.BORDER, focused_border_color=theme.ACCENT_BLUE)
    context_input = ft.TextField(label="Kontext (optional)",
                                 border_color=theme.BORDER, focused_border_color=theme.ACCENT_BLUE)
    priority_dd = ft.Dropdown(
        label="Priorität",
        value="normal",
        options=[ft.dropdown.Option(p, PRIORITY_DISPLAY[p]) for p in PRIORITIES],
        border_color=theme.BORDER,
    )

    def _close(payload: dict | None) -> None:
        page.close(dlg)
        on_save(payload)

    def _save(_e=None) -> None:
        title = (title_input.value or "").strip()
        if not title:
            return
        _close({
            "title": title,
            "context": (context_input.value or "").strip() or None,
            "priority": priority_dd.value or "normal",
            "mode": "work",
        })

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text("Neues Todo", color=theme.TEXT_PRIMARY, weight="bold"),
        content=ft.Column([title_input, context_input, priority_dd], spacing=10, width=420, tight=True),
        actions=[
            ft.TextButton("Abbrechen", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=_save),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.new_todo import show_new_todo; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/new_todo.py
git commit -m "feat(flet): add new-todo dialog"
```

---

## Task 12: Tag-select dialog

**Files:**
- Create: `flet_app/dialogs/tag_select.py`

- [ ] **Step 1: Implement tag select dialog**

Create `flet_app/dialogs/tag_select.py`:

```python
"""Tag picker dialog used to change the tag of an existing log entry."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log.tags import TagRegistry

from flet_app import theme


def show_tag_select(
    page: ft.Page,
    tags: TagRegistry,
    current_key: str,
    on_select: Callable[[str | None], None],
) -> None:
    tag_list = list(tags)

    def _close(key: str | None) -> None:
        page.close(dlg)
        on_select(key)

    rows = []
    for tag in tag_list:
        is_current = (tag.key == current_key)
        rows.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(tag.symbol, color=tag.color, size=14, width=24),
                        ft.Text(tag.key, color=tag.color, weight="bold", size=13, width=100),
                        ft.Text(tag.name, color=theme.TEXT_DIM, size=12, expand=True),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                bgcolor=theme.BG_SELECTED if is_current else None,
                border_radius=4,
                on_click=lambda _e, k=tag.key: _close(k),
            )
        )

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text("Tag wählen", color=theme.TEXT_SECONDARY),
        content=ft.Column(rows, spacing=2, width=360, height=min(400, 50 * len(rows) + 20),
                          scroll="auto", tight=True),
        actions=[ft.TextButton("Abbrechen", on_click=lambda _e: _close(None))],
    )
    page.open(dlg)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.tag_select import show_tag_select; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/tag_select.py
git commit -m "feat(flet): add tag-select dialog"
```

---

## Task 13: Content edit dialog

**Files:**
- Create: `flet_app/dialogs/content_edit.py`

- [ ] **Step 1: Implement content edit dialog**

Create `flet_app/dialogs/content_edit.py`:

```python
"""Multi-line editor for an existing log entry's content."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme


def show_content_edit(
    page: ft.Page,
    initial: str,
    on_save: Callable[[str | None], None],
) -> None:
    field = ft.TextField(
        value=initial,
        multiline=True,
        min_lines=10,
        max_lines=20,
        autofocus=True,
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
    )

    def _close(value: str | None) -> None:
        page.close(dlg)
        on_save(value)

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text("Eintrag bearbeiten", color=theme.TEXT_SECONDARY),
        content=ft.Container(content=field, width=640),
        actions=[
            ft.TextButton("Abbrechen", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=lambda _e: _close(field.value or "")),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.content_edit import show_content_edit; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/content_edit.py
git commit -m "feat(flet): add content-edit dialog"
```

---

## Task 14: Focus session dialog with live timer

**Files:**
- Create: `flet_app/dialogs/focus.py`

- [ ] **Step 1: Implement focus dialog**

Create `flet_app/dialogs/focus.py`:

```python
"""Focus session dialog: live elapsed timer, preset selector, notes input.

Returns via callback:
  - {"action": "minimize"}                     — keep session running, hide dialog
  - {"action": "stop", "outcome": str,
     "elapsed_s": int, "notes": list[str]}     — end session, hand off to debriefing
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme

TIMER_PRESETS = [25, 45, 90, 0]
PRESET_LABELS = ["25 min", "45 min", "90 min", "Offen"]


def show_focus(
    page: ft.Page,
    todo: db.Todo,
    started_at: str,
    on_done: Callable[[dict], None],
) -> None:
    state = {
        "preset_idx": 1,
        "notes": [],
        "stopped": False,
    }
    started_dt = datetime.fromisoformat(started_at)

    title = ft.Text(f"Focus  ·  {todo.title[:40]}", color=theme.TEXT_PRIMARY, weight="bold", size=14)
    timer_label = ft.Text("", color=theme.STATUS_COLORS["active"], size=24, weight="bold")
    preset_label = ft.Text(PRESET_LABELS[state["preset_idx"]], color=theme.TEXT_SECONDARY, size=12)
    note_input = ft.TextField(
        hint_text="Notiz hinzufügen (Enter = speichern)",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
        on_submit=lambda _e: _add_note(),
    )
    notes_view = ft.Column([], spacing=2, scroll="auto", height=120)

    def _add_note() -> None:
        text = (note_input.value or "").strip()
        if not text:
            return
        state["notes"].append(text)
        notes_view.controls.append(ft.Text(f"• {text}", color=theme.TEXT_DIM, size=12))
        note_input.value = ""
        page.update()

    def _cycle_preset(_e=None) -> None:
        state["preset_idx"] = (state["preset_idx"] + 1) % len(TIMER_PRESETS)
        preset_label.value = PRESET_LABELS[state["preset_idx"]]
        page.update()

    def _elapsed_s() -> int:
        return int((datetime.now() - started_dt).total_seconds())

    def _fmt(elapsed: int) -> str:
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _tick() -> None:
        while not state["stopped"]:
            elapsed = _elapsed_s()
            timer_label.value = _fmt(elapsed)
            try:
                page.update()
            except Exception:
                break
            threading.Event().wait(1)

    def _close_with(payload: dict) -> None:
        state["stopped"] = True
        page.close(dlg)
        on_done(payload)

    def _minimize(_e=None) -> None:
        _close_with({"action": "minimize"})

    def _stop(outcome: str) -> None:
        _close_with({
            "action": "stop",
            "outcome": outcome,
            "elapsed_s": _elapsed_s(),
            "notes": state["notes"],
        })

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=title,
        content=ft.Column(
            [
                ft.Row([timer_label, preset_label,
                        ft.IconButton(ft.Icons.TIMER, tooltip="Preset wechseln", on_click=_cycle_preset)],
                       alignment="center", vertical_alignment="center", spacing=12),
                ft.Divider(color=theme.BORDER),
                note_input,
                notes_view,
            ],
            width=520, spacing=10, tight=True,
        ),
        actions=[
            ft.TextButton("Minimieren (Esc)", on_click=_minimize),
            ft.OutlinedButton("Blockiert", on_click=lambda _e: _stop("blocked")),
            ft.OutlinedButton("Weiter offen", on_click=lambda _e: _stop("open")),
            ft.FilledButton("Gelöst", on_click=lambda _e: _stop("solved"),
                            style=ft.ButtonStyle(bgcolor=theme.STATUS_COLORS["active"], color="#000000")),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
    threading.Thread(target=_tick, daemon=True).start()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.focus import show_focus; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/focus.py
git commit -m "feat(flet): add focus session dialog with live timer"
```

---

## Task 15: Debriefing dialog

**Files:**
- Create: `flet_app/dialogs/debriefing.py`

- [ ] **Step 1: Implement debriefing dialog**

Create `flet_app/dialogs/debriefing.py`:

```python
"""Debriefing dialog after a focus session — captures outcome + log entry."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme

OUTCOMES = ["solved", "open", "blocked"]
OUTCOME_DISPLAY = {"solved": "✓ Gelöst", "open": "↻ Weiter offen", "blocked": "✕ Blockiert"}


def _fmt_duration(seconds: int) -> str:
    m = seconds // 60
    h = m // 60
    rm = m % 60
    if h == 0:
        return f"{m} min"
    return f"{h}h {rm:02d}min"


def show_debriefing(
    page: ft.Page,
    todo_title: str,
    elapsed_s: int,
    suggested_outcome: str,
    on_done: Callable[[dict | None], None],
) -> None:
    initial = suggested_outcome if suggested_outcome in OUTCOMES else "open"
    outcome_dd = ft.Dropdown(
        label="Ergebnis",
        value=initial,
        options=[ft.dropdown.Option(o, OUTCOME_DISPLAY[o]) for o in OUTCOMES],
        border_color=theme.BORDER,
    )
    log_input = ft.TextField(
        label="Eintrag fürs Tages-Log",
        hint_text="Kurz beschreiben was passiert ist…",
        autofocus=True, multiline=True, min_lines=2, max_lines=4,
        border_color=theme.BORDER, focused_border_color=theme.ACCENT_BLUE,
    )

    def _close(payload: dict | None) -> None:
        page.close(dlg)
        on_done(payload)

    def _save(_e=None) -> None:
        _close({"outcome": outcome_dd.value or "open", "log_entry": (log_input.value or "").strip()})

    dlg = ft.AlertDialog(
        modal=True, bgcolor=theme.BG_PANEL,
        title=ft.Text(f"Session abgeschlossen  ·  {todo_title[:40]}  ·  {_fmt_duration(elapsed_s)}",
                      color=theme.TEXT_PRIMARY, weight="bold"),
        content=ft.Column([outcome_dd, log_input], spacing=10, width=480, tight=True),
        actions=[
            ft.TextButton("Ohne Eintrag", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=_save),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.debriefing import show_debriefing; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/debriefing.py
git commit -m "feat(flet): add debriefing dialog"
```

---

## Task 16: Weekly review dialog

**Files:**
- Create: `flet_app/dialogs/weekly.py`

- [ ] **Step 1: Implement weekly review dialog**

Create `flet_app/dialogs/weekly.py`:

```python
"""Weekly review dialog — overlay summary of last 7 days."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


def _fmt_duration(seconds: int) -> str:
    if seconds == 0:
        return "–"
    m = seconds // 60
    h = m // 60
    rm = m % 60
    if h == 0:
        return f"{m}m"
    return f"{h}h {rm:02d}m"


def _energy_dots(value: float | None) -> str:
    if value is None:
        return "–"
    filled = round(value)
    return "●" * filled + "○" * (5 - filled) + f"  {value:.1f}/5"


def show_weekly(page: ft.Page, db_path: Path) -> None:
    state = {"offset": 0}
    body = ft.Column([], spacing=8, width=560, height=480, scroll="auto", tight=True)

    def _render() -> None:
        today = date.today()
        monday = today - timedelta(days=today.weekday() + 7 * state["offset"])
        sunday = monday + timedelta(days=6)
        iso_week = f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}"

        meta = db.day_meta_range(db_path, monday.isoformat(), sunday.isoformat()) \
            if hasattr(db, "day_meta_range") else []
        sessions = db.session_get_range(db_path, monday.isoformat(), sunday.isoformat()) \
            if hasattr(db, "session_get_range") else []
        todos = db.todo_list(db_path, mode="work")

        total_focus_s = sum(getattr(s, "duration_s", 0) for s in sessions)
        done = [t for t in todos if t.status == "done" and t.done_at and monday.isoformat() <= t.done_at[:10] <= sunday.isoformat()]
        open_now = [t for t in todos if t.status in ("open", "active", "paused")]

        energies = [m.morning_energy for m in meta if m.morning_energy is not None] if meta else []
        avg_energy = sum(energies) / len(energies) if energies else None

        body.controls = [
            ft.Text(f"KW {monday.isocalendar()[1]}  ·  {monday.strftime('%d. %b')} – {sunday.strftime('%d. %b %Y')}",
                    color=theme.TEXT_PRIMARY, size=14, weight="bold"),
            ft.Divider(color=theme.BORDER),
            ft.Text("ARBEIT", color=theme.ACCENT_BLUE, weight="bold"),
            ft.Text(f"Ø Energie  {_energy_dots(avg_energy)}", color=theme.TEXT_PRIMARY),
            ft.Text(f"{len(done)} done  ·  {len(open_now)} offen", color=theme.TEXT_PRIMARY),
            ft.Text(f"Fokus-Zeit:  {_fmt_duration(total_focus_s)}", color=theme.TEXT_PRIMARY),
            ft.Divider(color=theme.BORDER),
            ft.Text("DONE THIS WEEK", color=theme.STATUS_COLORS["done"], weight="bold"),
            *[ft.Text(f"  ✓  {t.title}", color=theme.TEXT_PRIMARY, size=12) for t in done] or
            [ft.Text("  (keine erledigten Todos)", color=theme.TEXT_DIM, italic=True)],
        ]
        page.update()

    def _prev(_e=None) -> None:
        state["offset"] += 1
        _render()

    def _next(_e=None) -> None:
        if state["offset"] > 0:
            state["offset"] -= 1
            _render()

    def _close(_e=None) -> None:
        page.close(dlg)

    dlg = ft.AlertDialog(
        modal=True, bgcolor=theme.BG_PANEL,
        title=ft.Text("Wochenrückblick", color=theme.TEXT_SECONDARY),
        content=body,
        actions=[
            ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Vorwoche", on_click=_prev),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Nächste", on_click=_next),
            ft.FilledButton("Schließen", on_click=_close),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
    _render()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.dialogs.weekly import show_weekly; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/dialogs/weekly.py
git commit -m "feat(flet): add weekly review dialog"
```

---

## Task 17: Async git push helper

**Files:**
- Create: `flet_app/git_push.py`

- [ ] **Step 1: Implement async git push helper**

Create `flet_app/git_push.py`:

```python
"""Async git add/commit/push of journal.db with toast feedback."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

from flet_app.widgets.toast import show_toast


async def _run(*args: str, cwd: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, (out + err).decode(errors="replace")


async def _push(page: ft.Page, db_path: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    cwd = str(db_path.parent)
    name = db_path.name

    show_toast(page, "git push: starting…", duration_ms=1500)

    rc, _ = await _run("git", "add", name, cwd=cwd)
    if rc != 0:
        show_toast(page, "git add fehlgeschlagen", severity="error", duration_ms=4000)
        return

    rc, out = await _run("git", "commit", "-m", f"update {timestamp}", cwd=cwd)
    if rc != 0:
        if "nothing to commit" in out:
            show_toast(page, "Keine Änderungen", duration_ms=2500)
        else:
            show_toast(page, "git commit fehlgeschlagen", severity="error", duration_ms=4000)
        return

    rc, _ = await _run("git", "push", cwd=cwd)
    if rc == 0:
        show_toast(page, f"journal.db gepushed [{timestamp}]", severity="success", duration_ms=3000)
    else:
        show_toast(page, "git push fehlgeschlagen", severity="error", duration_ms=4000)


def trigger_git_push(page: ft.Page, db_path: Path) -> None:
    """Run the async push in a background thread so the UI stays responsive."""
    def _runner() -> None:
        try:
            asyncio.run(_push(page, db_path))
        except Exception as e:
            try:
                show_toast(page, f"Push-Fehler: {e}", severity="error", duration_ms=4000)
            except Exception:
                pass

    threading.Thread(target=_runner, daemon=True).start()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.git_push import trigger_git_push; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/git_push.py
git commit -m "feat(flet): add async git push helper"
```

---

## Task 18: Keybinding dispatcher

**Files:**
- Create: `flet_app/keybindings.py`

- [ ] **Step 1: Implement keybinding dispatcher**

Create `flet_app/keybindings.py`:

```python
"""Central keyboard handler.

Translates Flet KeyboardEvent into named actions on the WorkApp instance.
Tab / Shift+Tab are context-aware:
  - Inside the log input: Shift+Tab cycles tags (Tab is reserved for app-wide panel cycle)
  - Anywhere else: Tab cycles panels forward, Shift+Tab cycles panels backward.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from flet_app.main import WorkApp


def attach(page: ft.Page, app: "WorkApp") -> None:
    page.on_keyboard_event = lambda e: _dispatch(e, app)


def _dispatch(e: ft.KeyboardEvent, app: "WorkApp") -> None:
    key = e.key
    shift = e.shift
    in_input = app.input_focused

    # Tab handling — context-aware
    if key == "Tab":
        if in_input and shift:
            app.action_prev_tag()
            return
        if not in_input:
            app.action_cycle_panel(direction=-1 if shift else 1)
            return
        # In input + plain Tab: let Flet do default focus handling
        return

    if in_input:
        # Inside the input we only care about Shift+Tab (handled above) and let
        # everything else flow to the TextField.
        return

    if key == "Q":
        app.page.window.close()
    elif key == "R":
        app.action_refresh_all()
    elif key == "F":
        app.action_start_focus()
    elif key == "A":
        app.action_add_todo()
    elif key == "M":
        app.action_toggle_content()
    elif key == "T":
        app.action_toggle_todos()
    elif key == "W":
        app.action_open_weekly()
    elif key == "V":
        app.action_view_latest()
    elif key == "E":
        app.action_edit_entry()
    elif key == "C":
        app.action_change_tag()
    elif key == "P" and shift:
        app.action_git_push_db()
    elif key == "B":
        app.action_prev_filter()
    elif key == "N":
        if app.last_action_was_filter:
            app.action_next_filter()
        else:
            app.action_focus_log_input()
    elif key == " ":
        app.action_focus_log_input()
    elif key in ("Arrow Up", "K"):
        app.action_todo_up()
    elif key in ("Arrow Down", "J"):
        app.action_todo_down()
    elif key == "Enter":
        app.action_todo_activate()
    elif key == "D":
        if shift:
            app.action_delete_entry()
        else:
            app.action_todo_done()
    elif key == "X":
        app.action_todo_delete()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from flet_app.keybindings import attach; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/keybindings.py
git commit -m "feat(flet): add keyboard dispatcher with context-aware Tab"
```

---

## Task 19: Main app — wire everything together

**Files:**
- Create: `flet_app/main.py`

- [ ] **Step 1: Implement WorkApp and entry point**

Create `flet_app/main.py`:

```python
"""Main Flet app — wires panels, state, dialogs, keybindings, live timer."""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime
from pathlib import Path

import flet as ft

from tui_log import db_utils as db
from tui_log.config import AppConfig

from flet_app import theme
from flet_app.state import AppState
from flet_app.panels.log_panel import LogPanel
from flet_app.panels.content_panel import ContentPanel
from flet_app.panels.todo_panel import TodoPanel
from flet_app.dialogs.confirm import show_confirm
from flet_app.dialogs.new_todo import show_new_todo
from flet_app.dialogs.tag_select import show_tag_select
from flet_app.dialogs.content_edit import show_content_edit
from flet_app.dialogs.focus import show_focus
from flet_app.dialogs.debriefing import show_debriefing
from flet_app.dialogs.weekly import show_weekly
from flet_app.git_push import trigger_git_push
from flet_app.widgets.toast import show_toast
from flet_app import keybindings


PANEL_ORDER = ["log", "content", "todo"]


class WorkApp:
    def __init__(self, page: ft.Page, cfg: AppConfig) -> None:
        self.page = page
        self.cfg = cfg

        work_tags = cfg.tags.by_category("work") + cfg.tags.by_category("any")
        self.state = AppState(db_path=cfg.db_path, tags=cfg.tags, work_tags=work_tags)
        self.state.load_all()

        self.log_panel = LogPanel(
            self.state,
            on_entry_select=self._on_entry_select,
            on_log_submit=self._on_log_submit,
            on_input_focus_change=self._on_input_focus_change,
        )
        self.content_panel = ContentPanel()
        self.todo_panel = TodoPanel(self.state, on_todo_select=self._on_todo_select)

        self.last_action_was_filter = False
        self.input_focused = False
        self._panel_idx = 0
        self._stop_clock = False

        self.state.on_change = self._refresh_all_panels

    # ── lifecycle ─────────────────────────────────────────────────────────

    def setup_page(self) -> None:
        self.page.title = "tui-log — daily journal"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = theme.BG_BASE
        self.page.padding = 8
        self.page.window.width = 1400
        self.page.window.height = 900
        self.page.window.min_width = 900
        self.page.window.min_height = 600
        self.page.window.center()

        self.page.add(
            ft.Row(
                [self.log_panel, self.content_panel, self.todo_panel],
                expand=True, spacing=8,
            )
        )
        self._refresh_all_panels()
        self._show_displayed_entry()

        keybindings.attach(self.page, self)
        self._start_clock()

    # ── refresh ───────────────────────────────────────────────────────────

    def _refresh_all_panels(self) -> None:
        self.log_panel.render()
        self.todo_panel.render()
        self._show_displayed_entry()

    def _show_displayed_entry(self) -> None:
        entry = None
        if self.state.displayed_entry_id is not None:
            entry = next((e for e in self.state.log_entries if e.id == self.state.displayed_entry_id), None)
        self.content_panel.show_entry(entry)

    # ── live clock for active session ─────────────────────────────────────

    def _start_clock(self) -> None:
        def _tick() -> None:
            while not self._stop_clock:
                if self.state.active_session:
                    started = datetime.fromisoformat(self.state.active_session.started_at)
                    elapsed = self.state.active_session_base_s + int((datetime.now() - started).total_seconds())
                    h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
                    timer = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                    label = f"  ▶  {self.state.active_session_title}  ·  {timer}"
                    try:
                        self.todo_panel.update_session_timer(label)
                    except Exception:
                        break
                else:
                    try:
                        self.todo_panel.update_session_timer(None)
                    except Exception:
                        break
                threading.Event().wait(1)

        threading.Thread(target=_tick, daemon=True).start()

    # ── selection callbacks ───────────────────────────────────────────────

    def _on_entry_select(self, entry: db.LogEntry) -> None:
        self.state.displayed_entry_id = entry.id
        self._show_displayed_entry()

    def _on_input_focus_change(self, has_focus: bool) -> None:
        self.input_focused = has_focus

    def _on_todo_select(self, todo: db.Todo) -> None:
        ids = [t.id for t in self.state.todos]
        if todo.id in ids:
            self.state.todo_idx = ids.index(todo.id)
            self.todo_panel.render()

    def _on_log_submit(self, text: str) -> None:
        if not self.state.work_tags:
            return
        tag_key = self.state.work_tags[self.state.tag_idx].key
        db.log_add(self.state.db_path, tag_key=tag_key, content=text, mode="work")
        self.state.load_log()
        self._refresh_all_panels()

    # ── actions ───────────────────────────────────────────────────────────

    def action_focus_log_input(self) -> None:
        self.log_panel.focus_input()
        self.last_action_was_filter = False

    def action_next_tag(self) -> None:
        self.state.cycle_tag(1)
        self.log_panel.render()

    def action_prev_tag(self) -> None:
        self.state.cycle_tag(-1)
        self.log_panel.render()

    def action_next_filter(self) -> None:
        self.state.cycle_filter(1)
        self.log_panel.render()
        self.last_action_was_filter = True

    def action_prev_filter(self) -> None:
        self.state.cycle_filter(-1)
        self.log_panel.render()
        self.last_action_was_filter = True

    def action_view_latest(self) -> None:
        if self.state.log_entries:
            self.state.displayed_entry_id = self.state.log_entries[0].id
            self._show_displayed_entry()

    def action_refresh_all(self) -> None:
        self.state.load_all()
        self._refresh_all_panels()
        show_toast(self.page, "Aktualisiert.")

    def action_toggle_todos(self) -> None:
        self.todo_panel.visible = not self.todo_panel.visible
        self.todo_panel.update()

    def action_toggle_content(self) -> None:
        self.content_panel.visible = not self.content_panel.visible
        self.content_panel.update()

    def action_cycle_panel(self, direction: int = 1) -> None:
        self._panel_idx = (self._panel_idx + direction) % len(PANEL_ORDER)
        target = PANEL_ORDER[self._panel_idx]
        if target == "log":
            self.log_panel.focus_input()

    def action_todo_up(self) -> None:
        if self.state.todos and self.state.todo_idx > 0:
            self.state.todo_idx -= 1
            self.todo_panel.render()

    def action_todo_down(self) -> None:
        if self.state.todos and self.state.todo_idx < len(self.state.todos) - 1:
            self.state.todo_idx += 1
            self.todo_panel.render()

    def action_todo_activate(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status in ("open", "paused"):
            db.todo_set_status(self.state.db_path, todo.id, "active")
            show_toast(self.page, f"▶  {todo.title[:40]}")
        elif todo.status == "active":
            db.todo_set_status(self.state.db_path, todo.id, "paused")
            show_toast(self.page, f"‖  {todo.title[:40]} pausiert")
        self.state.load_todos()
        self.todo_panel.render()

    def action_todo_done(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status == "done":
            return
        if self.state.active_session and self.state.active_session.todo_id == todo.id:
            db.session_end(self.state.db_path, self.state.active_session.id, outcome="solved", log_entry="")
            self.state.check_active_session()
        db.todo_set_status(self.state.db_path, todo.id, "done")
        db.log_add(self.state.db_path, tag_key="done", content=todo.title, mode="work")
        self.state.load_todos()
        self.state.load_log()
        self._refresh_all_panels()
        show_toast(self.page, f"✓  {todo.title[:40]}", severity="success")

    def action_todo_delete(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status == "cancelled":
            return

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            if self.state.active_session and self.state.active_session.todo_id == todo.id:
                db.session_end(self.state.db_path, self.state.active_session.id, outcome="open", log_entry="")
                self.state.check_active_session()
            db.todo_set_status(self.state.db_path, todo.id, "cancelled")
            self.state.load_todos()
            self.todo_panel.render()
            show_toast(self.page, f"✗  '{todo.title[:40]}' cancelled")

        show_confirm(self.page, f"'{todo.title[:50]}' wirklich canceln?", _on_confirm)

    def action_add_todo(self) -> None:
        prefill = self.log_panel.input.value or ""

        def _on_save(payload: dict | None) -> None:
            if not payload:
                return
            db.todo_add(
                self.state.db_path,
                title=payload["title"], context=payload["context"],
                priority=payload["priority"], mode=payload["mode"],
            )
            if prefill:
                self.log_panel.input.value = ""
            self.state.load_todos()
            self._refresh_all_panels()
            show_toast(self.page, f"Todo angelegt: {payload['title'][:40]}", severity="success")

        show_new_todo(self.page, _on_save, prefill_title=prefill)

    def action_edit_entry(self) -> None:
        if not self.state.displayed_entry_id:
            show_toast(self.page, "Kein Eintrag ausgewählt")
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return

        def _on_save(content: str | None) -> None:
            if content is None:
                return
            try:
                db.log_update(self.state.db_path, entry.id, content=content)
                self.state.load_log()
                self._refresh_all_panels()
                show_toast(self.page, "Eintrag gespeichert", severity="success")
            except Exception as e:
                logging.error(f"edit_entry failed:\n{traceback.format_exc()}")
                show_toast(self.page, f"Fehler: {e}", severity="error", duration_ms=4000)

        show_content_edit(self.page, entry.content, _on_save)

    def action_change_tag(self) -> None:
        if not self.state.displayed_entry_id:
            show_toast(self.page, "Kein Eintrag ausgewählt")
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return

        def _on_select(new_key: str | None) -> None:
            if new_key is None or new_key == entry.tag_key:
                return
            db.log_update(self.state.db_path, entry.id, tag_key=new_key)
            self.state.load_log()
            self._refresh_all_panels()
            show_toast(self.page, f"Tag → {new_key}", severity="success")

        show_tag_select(self.page, self.state.tags, entry.tag_key, _on_select)

    def action_delete_entry(self) -> None:
        if not self.state.displayed_entry_id:
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return
        preview = entry.content.split("\n", 1)[0][:50]

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            db.log_delete(self.state.db_path, entry.id)
            self.state.displayed_entry_id = None
            self.state.load_log()
            self._refresh_all_panels()
            show_toast(self.page, "Eintrag gelöscht")

        show_confirm(self.page, f"Eintrag löschen: '{preview}'?", _on_confirm)

    def action_open_weekly(self) -> None:
        show_weekly(self.page, self.state.db_path)

    def action_git_push_db(self) -> None:
        trigger_git_push(self.page, self.state.db_path)

    def action_start_focus(self) -> None:
        if not self.state.todos:
            show_toast(self.page, "Keine offenen Todos.", severity="warning")
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status not in ("open", "paused", "active"):
            candidates = [t for t in self.state.todos if t.status in ("open", "paused", "active")]
            if not candidates:
                show_toast(self.page, "Keine offenen Todos.", severity="warning")
                return
            todo = candidates[0]

        existing = db.session_get_active(self.state.db_path)
        if existing:
            if existing.todo_id == todo.id:
                db.session_end(self.state.db_path, existing.id, outcome="open", log_entry="")
                self.state.check_active_session()
                self.state.load_todos()
                self._refresh_all_panels()
                show_toast(self.page, f"Focus beendet: {todo.title[:40]}")
                return
            db.session_end(self.state.db_path, existing.id, outcome="open", log_entry="")

        session = db.session_start(self.state.db_path, todo.id)
        self.state.check_active_session()
        self._refresh_all_panels()

        def _on_focus_done(payload: dict) -> None:
            if payload.get("action") == "minimize":
                return

            def _on_debrief(debrief: dict | None) -> None:
                try:
                    if debrief is None:
                        db.session_end(self.state.db_path, session.id,
                                       outcome=payload["outcome"], log_entry="")
                    else:
                        db.session_end(self.state.db_path, session.id,
                                       outcome=debrief["outcome"], log_entry=debrief["log_entry"])
                        if debrief["log_entry"]:
                            tag_key = "done" if debrief["outcome"] == "solved" else "block"
                            db.log_add(self.state.db_path, tag_key=tag_key,
                                       content=debrief["log_entry"], mode="work", todo_id=todo.id)
                        for note in payload.get("notes", []):
                            db.note_add(self.state.db_path, todo.id, note, session_id=session.id)
                    self.state.check_active_session()
                    self.state.load_all()
                    self._refresh_all_panels()
                except Exception as e:
                    logging.error(f"on_debrief failed:\n{traceback.format_exc()}")
                    show_toast(self.page, f"Fehler: {e}", severity="error", duration_ms=4000)

            show_debriefing(self.page, todo.title, payload["elapsed_s"], payload["outcome"], _on_debrief)

        show_focus(self.page, todo, session.started_at, _on_focus_done)


# ── entry point ───────────────────────────────────────────────────────────

def run(cfg: AppConfig) -> None:
    def _target(page: ft.Page) -> None:
        app = WorkApp(page, cfg)
        app.setup_page()

    ft.app(target=_target)
```

- [ ] **Step 2: Verify import (no syntax errors)**

Run: `python -c "from flet_app.main import run; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add flet_app/main.py
git commit -m "feat(flet): add main WorkApp with all panels, dialogs, actions"
```

---

## Task 20: Wire entry point — replace Textual launcher

**Files:**
- Modify: `tui_log/__main__.py` (lines 85-87)
- Modify: `work_app.py` (root shim — verify still calls `tui_log.__main__.main()`)

- [ ] **Step 1: Modify `tui_log/__main__.py` to launch Flet app**

Replace lines 84-90 (the section starting `# 3. App starten` and ending before `# 4. WAL-Checkpoint`) with:

```python
    # 3. App starten (Flet desktop)
    from flet_app.main import run
    try:
        run(cfg)
    except Exception as e:
        logging.error(f"Unbehandelter Fehler:\n{traceback.format_exc()}")
        print(f"\n[Fehler] {e}\nDetails in: {log_path}")
```

- [ ] **Step 2: Verify root shim `work_app.py` still works**

Read `D:/Projects/tui-log/work_app.py`. Confirm it calls `tui_log.__main__.main()` (no change needed). If it imports `WorkApp` directly from `tui_log.work_app`, change it to:

```python
"""Repo entry point — adds repo to sys.path and runs the Flet app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tui_log.__main__ import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test — launch the app**

Run: `python work_app.py`
Expected: Flet window opens at 1400×900, dark theme, three panels visible (log left, content middle, todo right). Header bars show counts. Log entries from `journal.db` appear in the left list. Quit with `q` or close the window.

- [ ] **Step 4: Commit**

```bash
git add tui_log/__main__.py work_app.py
git commit -m "feat(flet): switch entry point from Textual to Flet"
```

---

## Task 21: Manual UI verification

**Files:** none — manual exercise of the running app.

- [ ] **Step 1: Launch app and verify each keybinding**

Run: `python work_app.py`

Verify in this order, fixing each bug as it appears (commit fixes individually with `fix(flet): ...`):

1. `Space` or `n` (when nothing else triggered) → log input gains focus.
2. Type `test` + `Enter` → entry appears in log list, input clears.
3. `Shift+Tab` while in input → tag chip cycles forward through work tags.
4. Click a log entry → middle content panel shows full content.
5. `b` / `n` (when not in input) → filter chips cycle.
6. `e` → content edit dialog opens with current entry text.
7. `c` → tag select dialog opens.
8. `Shift+D` → confirm dialog → entry deleted.
9. `a` → new todo dialog opens; save → todo appears in right panel.
10. Arrow Up / Down → todo selection moves (highlighted with blue left border).
11. `Enter` on todo → status toggles open ↔ active (icon changes).
12. `f` on todo → focus dialog opens with live timer ticking each second.
13. Inside focus dialog: type a note + Enter → appears in notes list.
14. `Esc` (close button "Minimieren") → dialog hides; session bar in todo panel keeps ticking.
15. `f` again on same todo → debriefing dialog appears; save → log entry written, session ended.
16. `d` on todo → todo marked done.
17. `x` on todo → confirm → todo cancelled.
18. `t` → todo panel hides; `t` again → reappears.
19. `m` → content panel hides; `m` again → reappears.
20. `Tab` (outside input) → focus moves between panels visually.
21. `w` → weekly review dialog opens; arrows page weeks.
22. `r` → toast "Aktualisiert."
23. `Shift+P` → toast "git push: starting…" then result toast.
24. Verify `journal.db` is unchanged structurally (no new tables / columns).

Run: `python tests/test_db_utils.py`
Expected: all existing DB tests still pass.

- [ ] **Step 2: Commit any UI fix-ups discovered during verification**

For each fix: small focused commit `fix(flet): <what>`.

---

## Task 22: Build standalone Windows .exe

**Files:** none — build artifacts only.

- [ ] **Step 1: Run Flet build for Windows**

Run: `flet build windows`
Expected: produces `build/windows/` containing `tui-log.exe` and supporting DLLs. First run may take several minutes.

- [ ] **Step 2: Verify .exe launches**

Run: `./build/windows/tui-log.exe` (or double-click)
Expected: window opens identically to `python work_app.py`. The bundled app should find or create its `journal.db` next to a discoverable `config.toml`.

If `config.toml` is not discoverable inside the bundle, add a small launcher fix: in `flet_app/main.py`, before `AppConfig.load`, fall back to `~/.config/tui-log/config.toml`. Verify the fallback already exists in `tui_log/config.py:_default_config_path` — if so, document the user setup step.

- [ ] **Step 3: Commit build config tweaks (if any)**

If `pyproject.toml` needed changes to bundle correctly:

```bash
git add pyproject.toml
git commit -m "build: tune flet build config for windows"
```

---

## Task 23: Update CLAUDE.md and remove old Textual code

**Files:**
- Modify: `CLAUDE.md`
- Delete: `tui_log/work_app.py`, `tui_log/work.tcss`, `tui_log/widgets/` (whole dir), `tui_log/views/` (whole dir)

- [ ] **Step 1: Verify nothing imports the old Textual modules**

Run: `grep -rn "from .work_app\|from .widgets\|from .views\|from tui_log.work_app\|from tui_log.widgets\|from tui_log.views\|import textual" --include="*.py" .`
Expected: no matches in `flet_app/`, `tests/`, `tui_log/__main__.py`, or `work_app.py`. Matches inside the to-be-deleted files themselves are fine.

If any active file still imports these, fix the import before deleting.

- [ ] **Step 2: Delete old Textual files**

```bash
git rm tui_log/work_app.py tui_log/work.tcss
git rm -r tui_log/widgets tui_log/views
```

- [ ] **Step 3: Update CLAUDE.md**

Open `CLAUDE.md` and replace the `## Architecture` section (and the `### Three-panel layout` and `### Keybindings` subsections) with a Flet-oriented version:

```markdown
## Architecture

### Entry point

`work_app.py` (root) is a thin shim — it adds the repo to `sys.path` and calls `tui_log.__main__.main()`.

`tui_log/__main__.py` does: parse args → load `AppConfig` → `init_db` → `project_upsert_from_config` → start Flet app via `flet_app.main.run(cfg)`. WAL checkpoint runs on clean exit.

### Backend (unchanged)

`tui_log/` keeps the data layer:
- `config.py`, `tags.py`, `mode.py`, `schema.py`, `db_utils.py`
- SQLite WAL DB at `journal.db` next to `config.toml`
- All CRUD lives in `db_utils.py`; never write SQL elsewhere.

### Flet UI (`flet_app/`)

```
flet_app/
  main.py            # WorkApp + ft.app entry
  state.py           # AppState — wraps DB, holds reactive UI state
  theme.py           # color/style constants (dark theme)
  keybindings.py     # context-aware key dispatcher
  git_push.py        # async git add/commit/push of journal.db
  panels/
    log_panel.py     # left column
    content_panel.py # middle column (markdown view)
    todo_panel.py    # right column
  dialogs/
    confirm.py
    new_todo.py
    tag_select.py
    content_edit.py
    focus.py         # live-timer focus session
    debriefing.py
    weekly.py        # weekly review overlay
  widgets/
    log_entry_row.py
    todo_row.py
    toast.py
```

Single window, three columns. Modals are Flet `AlertDialog` overlays.

### Keybindings

| Key | Action |
|-----|--------|
| `Space` / `n` | Focus log input |
| `Tab` | Cycle panels forward (log → content → todo → log) |
| `Shift+Tab` (outside input) | Cycle panels backward |
| `Shift+Tab` (inside input) | Cycle tag |
| `f` | Start/toggle focus session on selected todo |
| `a` | New todo dialog |
| `m` | Toggle content panel |
| `t` | Toggle todo panel |
| `w` | Open weekly review dialog |
| `v` | Show latest log entry in content panel |
| `e` | Edit currently displayed log entry |
| `c` | Change tag of displayed entry |
| `b` / `n` | Cycle log filter backward / forward |
| `Shift+P` | Async git add+commit+push `journal.db` (toast feedback) |
| `r` | Reload everything from DB |
| `q` | Quit |
| `↑`/`k`, `↓`/`j` | Navigate todo list |
| `Enter` | Toggle todo active/paused |
| `d` | Mark todo done |
| `x` | Cancel todo (with confirm) |
| `Shift+D` | Delete displayed log entry (with confirm) |

### Build

```bash
flet build windows
```

Output: `build/windows/tui-log.exe` + bundled runtime.
```

Then update the `## Commands` section's `# Run the app` block: keep `python work_app.py` and `python work_app.py --config /path/to/config.toml` (these still work). Remove any references to Textual.

- [ ] **Step 4: Smoke test after deletion**

Run: `python work_app.py`
Expected: app launches identically.

Run: `python tests/test_db_utils.py && python tests/test_state.py`
Expected: both test runs end with `OK`.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for flet migration; remove textual code"
```
