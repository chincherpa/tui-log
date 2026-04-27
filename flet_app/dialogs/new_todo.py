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
        page.pop_dialog()
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
    page.show_dialog(dlg)
