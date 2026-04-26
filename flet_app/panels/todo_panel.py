"""Right column: active session bar + todo list."""

from __future__ import annotations

from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme
from flet_app.state import AppState
from flet_app.widgets.todo_row import build_todo_row


class TodoPanel(ft.Container):
    def __init__(self, state: AppState, on_todo_select: Callable[[db.Todo], None]) -> None:
        self.state = state
        self.on_todo_select = on_todo_select

        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.session_bar = ft.Container(
            content=ft.Text("", color=theme.STATUS_COLORS["active"], size=12, weight="bold"),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.BG_SELECTED,
            border_radius=4,
            visible=False,
        )
        self.list_view = ft.ListView(spacing=4, padding=4, expand=True)

        super().__init__(
            content=ft.Column([self.title, self.session_bar, self.list_view], spacing=6, expand=True),
            padding=8,
            bgcolor=theme.BG_PANEL,
            border=ft.border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def render(self) -> None:
        self._render_title()
        self._render_list()
        self.update()

    def update_session_timer(self, label: str | None) -> None:
        if label is None:
            self.session_bar.visible = False
        else:
            self.session_bar.visible = True
            self.session_bar.content = ft.Text(label, color=theme.STATUS_COLORS["active"], size=12, weight="bold")
        self.session_bar.update()

    def _render_title(self) -> None:
        active_cnt = sum(1 for t in self.state.todos if t.status in ("open", "active", "paused"))
        done_cnt   = sum(1 for t in self.state.todos if t.status == "done")
        self.title.value = f"  ✅ TODOS  ·  {active_cnt} offen  ·  {done_cnt} done"

    def _render_list(self) -> None:
        self.list_view.controls.clear()
        if not self.state.todos:
            self.list_view.controls.append(
                ft.Text("  (keine Todos – [a] um eines anzulegen)", color=theme.TEXT_DIM, italic=True)
            )
            return
        focus_id = self.state.active_session.todo_id if self.state.active_session else None
        for i, todo in enumerate(self.state.todos):
            self.list_view.controls.append(
                build_todo_row(
                    todo,
                    selected=(i == self.state.todo_idx),
                    is_focus=(todo.id == focus_id),
                    on_click=self.on_todo_select,
                )
            )
