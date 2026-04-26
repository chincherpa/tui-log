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
