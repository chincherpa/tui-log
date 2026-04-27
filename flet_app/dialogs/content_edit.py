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
        page.pop_dialog()
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
    page.show_dialog(dlg)
