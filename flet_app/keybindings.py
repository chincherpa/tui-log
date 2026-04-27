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
        if in_input:
            if shift:
                app.action_prev_tag()
            else:
                app.action_next_tag()
            return
        app.action_cycle_panel(direction=-1 if shift else 1)
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
