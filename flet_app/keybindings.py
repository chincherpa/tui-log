"""Central keyboard handler.

Translates Flet KeyboardEvent into named actions on the WorkApp instance.
Tab / Shift+Tab are context-aware:
  - Inside the log input: Tab cycles tag forward, Shift+Tab backward
  - Anywhere else: Tab cycles active panel forward, Shift+Tab backward
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from flet_app.main import WorkApp

SPACE_KEYS = {" ", "Space", "Spacebar"}
ARROW_UP_KEYS = {"Arrow Up", "ArrowUp", "Up"}
ARROW_DOWN_KEYS = {"Arrow Down", "ArrowDown", "Down"}

def attach(page: ft.Page, app: "WorkApp") -> None:
    page.on_keyboard_event = lambda e: _dispatch(e, app)

def _dispatch(e: ft.KeyboardEvent, app: "WorkApp") -> None:
    key = e.key
    shift = e.shift

    if key in ("Escape", "Esc"):
        handler = getattr(app, "dialog_escape_handler", None)
        if handler is not None:
            try:
                handler()
            except Exception:
                pass
            return

    if app.dialog_open:
        return

    # Tab handling — context-aware
    if key == "Tab":
        app.action_cycle_panel(direction=-1 if shift else 1)
        return

    if app.input_focused:
        # Inside the input, all other keys flow to the TextField.
        return

    if key == "Enter":
        app.action_todo_detail()
    elif key in SPACE_KEYS:
        app.action_todo_activate()
    elif key == "A":
        app.action_add_todo()
    elif key == "B":
        app.action_prev_filter()
    elif key == "C":
        app.action_change_tag()
    elif key == "D":
        if shift:
            app.action_delete_entry()
        else:
            app.action_todo_done()
    elif key == "E":
        app.action_edit_entry()
    elif key == "F":
        app.action_start_focus()
    elif key == "L":
        app.action_focus_log_input()
    elif key == "M":
        app.action_toggle_content()
    elif key == "N":
        app.action_next_filter()
    elif key == "P":
        app.action_prev_tag()
    elif key == "Q":
        app.action_quit()
    elif key == "R":
        app.action_refresh_all()
    elif key == "T":
        app.action_toggle_todos()
    elif key == "V":
        app.action_view_latest()
    elif key == "W":
        app.action_open_weekly()
    elif key == "X":
        app.action_todo_delete()
    elif key in ARROW_UP_KEYS:
        app.action_arrow(-1)
    elif key in ARROW_DOWN_KEYS:
        app.action_arrow(1)
