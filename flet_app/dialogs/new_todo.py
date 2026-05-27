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

    selected = {"value": "normal"}
    priority_label = ft.Text("Priorität", color=theme.TEXT_SECONDARY, size=12)
    priority_row = ft.Row([], spacing=6)

    def _build_priority_row() -> None:
        chips: list[ft.Control] = []
        for p in PRIORITIES:
            active = (selected["value"] == p)
            color = theme.PRIORITY_COLORS.get(p, theme.TEXT_PRIMARY)
            chips.append(
                ft.Container(
                    content=ft.Text(PRIORITY_DISPLAY[p],
                                    color="#000000" if active else color,
                                    weight="bold", size=13),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=color if active else theme.BG_SELECTED,
                    border=ft.Border.all(1, color),
                    border_radius=6,
                    on_click=lambda _e, k=p: _pick(k),
                )
            )
        priority_row.controls = chips

    def _pick(p: str) -> None:
        selected["value"] = p
        _build_priority_row()
        try:
            priority_row.update()
        except Exception:
            pass

    _build_priority_row()

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
            "priority": selected["value"],
            "mode": "work",
        })

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text("Neues Todo", color=theme.TEXT_PRIMARY, weight="bold"),
        content=ft.Column(
            [title_input, context_input, priority_label, priority_row],
            spacing=10, width=420, tight=True,
        ),
        actions=[
            ft.TextButton("Abbrechen", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=_save),
        ],
        actions_alignment="end",
    )
    page.show_dialog(dlg)
