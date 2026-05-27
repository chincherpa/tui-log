"""Single log entry row — displays time, tag chip, first line, body indicator."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db
from tui_log.tags import TagRegistry

from flet_app import theme

def _fmt_time(iso_dt: str) -> str:
    try:
        return iso_dt[11:16]
    except (TypeError, IndexError):
        return "??:??"

def build_log_entry_row(
    entry: db.LogEntry,
    tags: TagRegistry,
    *,
    selected: bool,
    on_click: Callable[[db.LogEntry], None],
) -> ft.Control:
    tag = tags.get(entry.tag_key)
    symbol = tag.symbol if tag else "·"
    color  = tag.color  if tag else theme.TEXT_SECONDARY
    time_s = _fmt_time(entry.created_at)
    first_line = entry.content.split("\n", 1)[0]
    has_body = "\n" in entry.content and entry.content.split("\n", 1)[1].strip()

    row = ft.Row(
        [
            ft.Text(time_s, color=theme.TEXT_DIM, size=12, width=44),
            ft.Container(
                content=ft.Text(f"{symbol} {entry.tag_key}", color=color, weight="bold", size=12),
                width=80,
            ),
            ft.Text(
                ("📄 " if has_body else "") + first_line,
                color=theme.TEXT_PRIMARY,
                size=13,
                expand=True,
                overflow="ellipsis",
                max_lines=1,
            ),
        ],
        spacing=8,
        vertical_alignment="center",
    )

    return ft.Container(
        content=row,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=theme.BG_SELECTED if selected else None,
        border_radius=4,
        on_click=lambda _e: on_click(entry),
    )

def build_date_separator(label: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(f"── {label} ──", color=theme.TEXT_DIM, size=11),
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
    )
