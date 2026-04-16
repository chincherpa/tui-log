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

### Entry point (`__main__.py`)

Parses args → loads `AppConfig` → calls `init_db` → starts `WorkApp`. A WAL checkpoint is run on clean exit.

### Mode detection (`mode.py`)

Returns `Mode.WORK` or `Mode.HANDOVER` based on current time and `schedule` from `config.toml`. Used only for the title bar label.

### Config (`config.py`)

`AppConfig.load()` reads `config.toml`. Config search order: explicit `--config` path → `./config.toml` → `~/.config/tui-log/config.toml`. The DB path (`journal.db`) is placed next to the resolved config file.

### Tags (`tags.py`)

Tags are defined in `config.toml` under `[tags.work]` and `[tags.any]`. `TagRegistry` builds the ordered list. The `LogInput` widget cycles tags with `Tab`/`Shift+Tab`.

### Database (`schema.py`, `db_utils.py`)

- SQLite with WAL mode, foreign keys ON, busy_timeout 3000ms.
- `get_connection()` is the sole connection factory — always use it.
- Migrations live in `_MIGRATIONS: dict[int, str]`. To add one: append a new key, increment `SCHEMA_VERSION`.
- All CRUD is in `db_utils.py`; no SQL outside that file or `schema.py`.

### App structure

| File | Role |
|------|------|
| `work_app.py` | Textual `App` — main layout, todo panel, session bar |
| `views/weekly.py` | Weekly review `Screen` (opened with `w`) |
| `widgets/focus.py` | Focus session modal with live timer |
| `widgets/debriefing.py` | Post-session outcome + log entry modal |
| `widgets/new_todo.py` | New todo modal |
| `widgets/log_input.py` | `Input` subclass — Tab cycles tags, suppresses focus cycle |
| `work.tcss` | Textual CSS for work-mode layout |

### Focus session lifecycle

`focus.py` starts a timer → `Esc` minimizes (timer keeps running, session bar in todo panel ticks) → `Ctrl+S` ends session → `debriefing.py` collects outcome → writes to `log_entries` + updates `todo.status` + saves notes to `todo_notes`.

## Extending

**New tag:** add to `config.toml` under `[tags.work]` or `[tags.any]` — available on next start.

**New migration:** add `_MIGRATIONS[N] = "ALTER TABLE ..."` in `schema.py`, increment `SCHEMA_VERSION`. Applied automatically on next start.
