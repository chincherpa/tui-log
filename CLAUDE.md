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
python tests/test_state.py
```

**Dependencies:** `pip install flet`. All else is stdlib (Python 3.11+).

**Error log:** written to `tui-log.log` next to `journal.db`.

## Architecture

### Entry point

`work_app.py` (root) is a thin shim — adds the repo to `sys.path` and calls `tui_log.__main__.main()`.

`tui_log/__main__.py` does: parse args → load `AppConfig` → `init_db` → `project_upsert_from_config` → call `flet_app.main.run(cfg)`. WAL checkpoint runs on clean exit.

The `tui_log/` package is **data-only**: config, DB schema/utils, tags, mode detection. No UI code lives there. All UI is in `flet_app/`.

### Config (`tui_log/config.py`)

`AppConfig.load()` reads `config.toml`. Search order: explicit `--config` → `./config.toml` → `~/.config/tui-log/config.toml`. DB path (`journal.db`) is placed next to the resolved config file.

### Database (`tui_log/schema.py`, `tui_log/db_utils.py`)

- SQLite with WAL mode, foreign keys ON, busy_timeout 3000ms.
- `get_connection()` is the sole connection factory — always use it.
- Migrations live in `_MIGRATIONS: dict[int, str]`. To add one: append new key, increment `SCHEMA_VERSION`.
- All CRUD in `db_utils.py`; no SQL outside that file or `schema.py`.
- Return types are dataclasses: `LogEntry`, `Todo`, `FocusSession`, `DayMeta`, etc.
- Todo statuses: `open → active → paused → done / dropped / cancelled`.
- Focus session outcomes: `solved`, `open`, `blocked`.

### Flet UI layer (`flet_app/`)

```
flet_app/
  main.py          # WorkApp class — wires panels, state, dialogs, clock, keybindings
  state.py         # AppState — loaded entities, filters, selection; on_change callback
  keybindings.py   # page.on_keyboard_event → WorkApp.action_*
  theme.py         # Color/style constants (BG_*, TEXT_*, STATUS_COLORS, etc.)
  panels/
    log_panel.py   # Left column: filter bar, carry-over bar, log list, text input
    content_panel.py # Middle column: read-only log entry detail
    todo_panel.py  # Right column: active session timer bar, todo list
  dialogs/         # Each dialog is a show_*(page, ..., callback) function
    confirm.py     # Generic yes/no confirm
    content_edit.py
    tag_select.py
    new_todo.py
    focus.py       # Focus session timer + minimize
    debriefing.py  # Post-session outcome + log entry
    weekly.py      # Weekly review
  widgets/
    log_entry_row.py
    todo_row.py
    toast.py       # show_toast(page, msg, severity, duration_ms)
  git_push.py      # trigger_git_push — runs git in background thread
```

### State and rendering

`AppState` holds all loaded data (log entries, todos, active session, filters, selection indices). Panels call `state.load_*()` methods and re-render themselves by reading from state. `WorkApp.state.on_change` is set to `_refresh_all_panels` so any action that mutates DB and calls `state.load_all()` triggers a full re-render automatically.

Panels extend `ft.Container` and expose a `render()` method that rebuilds their content. Dialogs are `show_*(page, ..., callback)` functions — they call `page.show_dialog(dlg)` and invoke the callback on completion (or `None` on cancel/Esc).

### Keybindings

`keybindings.attach(page, app)` registers `page.on_keyboard_event`. Keys are blocked while a dialog is open (`app.dialog_open`). Tab/Shift+Tab cycle active panel globally; inside the log input they cycle tags instead.

| Key | Action |
|-----|--------|
| `Space` / `N` (after non-filter) | Focus log input |
| `F` | Start/toggle focus session on selected todo |
| `A` | New todo modal |
| `M` | Toggle content panel |
| `T` | Toggle todo panel |
| `W` | Open weekly review |
| `V` | View latest log entry |
| `E` | Edit displayed log entry |
| `C` | Change tag of displayed entry |
| `B` / `N` (after filter) | Cycle log filter backward / forward |
| `Shift+D` | Delete log entry (confirm) |
| `D` | Mark selected todo done |
| `X` | Cancel selected todo (confirm) |
| `Enter` | Toggle todo active/paused |
| `R` | Reload all from DB |
| `Q` | Quit |
| `up`/`K`, `down`/`J` | Navigate (log list or todo list, context-aware) |
| `Tab` / `Shift+Tab` | Cycle active panel (or cycle tag when in input) |

### Focus session lifecycle

`show_focus` starts a timer dialog → "minimize" closes dialog but keeps session running (timer ticks in `WorkApp._start_clock`) → pressing `F` on the same todo calls `_finalize_session` → `show_debriefing` collects outcome + log entry → writes to `log_entries`, updates `todo_notes`.

## Extending

**New tag:** add to `config.toml` under `[tags.work]` or `[tags.any]` — available on next start.

**New migration:** add `_MIGRATIONS[N] = "ALTER TABLE ..."` in `tui_log/schema.py`, increment `SCHEMA_VERSION`. Applied automatically on next start.

**New dialog:** follow the `show_*(page, ..., callback)` pattern. Use `page.show_dialog` / `page.pop_dialog` — `WorkApp._wrap_dialog_tracking` patches these to maintain `app.dialog_open`.
