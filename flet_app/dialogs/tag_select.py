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
