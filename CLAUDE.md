# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
python work_app.py

# Use an alternative config
python work_app.py --config /path/to/config.toml

# Run tests (standalone runner, no pytest needed)
python tests/test_db_utils.py
```

**Dependencies:** `pip install textual` (>= 0.70.0). All else is stdlib (Python 3.11+).

**Error log:** written to `tui-log.log` next to `journal.db` (also `%APPDATA%\textual.log` for Textual internals).

## Architecture

### Entry point

`work_app.py` (root) is a thin shim — it adds the repo to `sys.path` and calls `tui_log.__main__.main()`.

`tui_log/__main__.py` does: parse args → load `AppConfig` → `init_db` → `project_upsert_from_config` → start `WorkApp`. WAL checkpoint runs on clean exit.

### Config (`config.py`)

`AppConfig.load()` reads `config.toml`. Search order: explicit `--config` → `./config.toml` → `~/.config/tui-log/config.toml`. DB path (`journal.db`) is placed next to the resolved config file. Projects can be declared in config.toml and are synced via `db.project_upsert_from_config`.

### Mode detection (`mode.py`)

Returns `Mode.WORK` or `Mode.HANDOVER` based on current time and `schedule` in config. Used only for the title bar label.

### Tags (`tags.py`)

Defined in `config.toml` under `[tags.work]` and `[tags.any]`. `TagRegistry` builds the ordered list. `LogInput` cycles tags with `Tab`/`Shift+Tab`.

### Database (`schema.py`, `db_utils.py`)

- SQLite with WAL mode, foreign keys ON, busy_timeout 3000ms.
- `get_connection()` is the sole connection factory — always use it.
- Migrations live in `_MIGRATIONS: dict[int, str]`. To add one: append a new key, increment `SCHEMA_VERSION`.
- All CRUD is in `db_utils.py`; no SQL outside that file or `schema.py`.
- Return types are dataclasses: `LogEntry`, `Todo`, `FocusSession`, `DayMeta`, etc.
- Todo statuses: `open → active → paused → done / dropped / cancelled`.
- Focus session outcomes: `solved`, `open`, `blocked`.

### Three-panel layout (`tui_log/work_app.py`)

```
┌── log-panel (left) ──┬── content-panel (mid) ──┬── todo-panel (right) ──┐
│ log-panel-title      │ content-panel-title      │ todo-panel-title       │
│ log-filter-bar       │ log-entry-content        │ active-session-bar     │
│ carry-over-bar       │   (ContentView)          │ todo-list-content      │
│ log-list-view        │                          │   (TodoListContent)    │
│ [tag] log-text-input │                          │                        │
└──────────────────────┴──────────────────────────┴────────────────────────┘
```

| File | Role |
|------|------|
| `tui_log/work_app.py` | Textual `App` — main layout, all keybindings, session bar |
| `views/weekly.py` | Weekly review `Screen` (opened with `w`) |
| `widgets/focus.py` | Focus session modal with live timer |
| `widgets/debriefing.py` | Post-session outcome + log entry modal |
| `widgets/new_todo.py` | New todo modal |
| `widgets/log_input.py` | `Input` subclass — Tab cycles tags, suppresses focus cycle |
| `widgets/content_view.py` | `ContentView` (read-only log detail), `ContentEditModal` (edit with `Ctrl+S`) |
| `work.tcss` | Textual CSS for work-mode layout |

### Keybindings (WorkApp)

| Key | Action |
|-----|--------|
| `Space` / `n` | Focus log input |
| `f` | Start/toggle focus session on selected todo |
| `a` | New todo modal |
| `m` | Toggle content/detail panel (middle column) |
| `t` | Toggle todo panel |
| `w` | Open weekly review screen |
| `v` | Refresh content panel to latest log entry |
| `e` | Edit currently displayed log entry (opens `ContentEditModal`) |
| `c` | Change tag of displayed entry (opens `TagSelectModal`) |
| `b` / `n` | Cycle log filter backward / forward |
| `Shift+P` | Git-add + commit + push `journal.db` |
| `r` | Reload everything from DB |
| `q` | Quit |
| `up`/`j`, `down`/`k` | Navigate todo list |
| `Enter` | Toggle todo active/paused |
| `d` | Mark todo done |
| `x` | Cancel todo (with confirm modal) |

### Focus session lifecycle

`focus.py` starts a timer → `Esc` minimizes (timer keeps running; session bar ticks) → `Ctrl+S` ends session → `debriefing.py` collects outcome → writes to `log_entries` + updates `todo.status` + saves notes to `todo_notes`.

## Extending

**New tag:** add to `config.toml` under `[tags.work]` or `[tags.any]` — available on next start.

**New migration:** add `_MIGRATIONS[N] = "ALTER TABLE ..."` in `schema.py`, increment `SCHEMA_VERSION`. Applied automatically on next start.

**Debug env vars:** `TUILOG_TEST_MODAL=1` — opens a minimal test modal instead of `FocusModal`. `TUILOG_MINIMAL_MODAL=1` — opens an inline minimal modal for mount-problem diagnosis.
