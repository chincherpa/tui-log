"""Two-line todo row: status icon, title, context, stats."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    h = m // 60
    if h == 0:
        return f"{m}m"
    return f"{h}h{m % 60:02d}"


PRIORITY_SYMBOLS = {"high": "▲", "normal": "●", "low": "▼"}


def build_todo_row(
    todo: db.Todo,
    *,
    selected: bool,
    is_focus: bool,
    on_click: Callable[[db.Todo], None],
) -> ft.Control:
    effective_status = "focus" if is_focus else todo.status
    icon = theme.STATUS_ICONS.get(effective_status, "○")
    color = theme.STATUS_COLORS.get(effective_status, theme.TEXT_PRIMARY)

    ctx = (todo.context or "")[:32]
    dur = _fmt_duration(todo.total_duration_s) if todo.total_duration_s else ""
    # sess = f"{todo.total_sessions}×" if todo.total_sessions else ""
    stats = f"{dur}".strip()

    prio_sym = PRIORITY_SYMBOLS.get(todo.priority, "·")
    prio_color = theme.PRIORITY_COLORS.get(todo.priority, theme.TEXT_DIM)

    line1_children = [
        ft.Text(icon, color=color, size=14, width=20),
        ft.Text(prio_sym, color=prio_color, size=13, width=14),
        ft.Text(todo.title, color=color, weight="bold", size=13, expand=True, overflow="ellipsis", max_lines=1),
    ]
    if stats:
        line1_children.append(ft.Text(stats, color=theme.TEXT_DIM, size=11))
    line1 = ft.Row(line1_children, spacing=4, vertical_alignment="center")

    line2_children = []
    if ctx:
        line2_children.append(ft.Text(ctx, color=theme.TEXT_SECONDARY, size=11))
    line2 = ft.Row(line2_children, spacing=8) if line2_children else ft.Container(height=0)

    return ft.Container(
        content=ft.Column([line1, line2], spacing=2),
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        bgcolor=theme.BG_SELECTED if selected else None,
        border=ft.border.only(left=ft.BorderSide(3, theme.ACCENT_BLUE)) if selected else None,
        border_radius=4,
        on_click=lambda _e: on_click(todo),
    )
