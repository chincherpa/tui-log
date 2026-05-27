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
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.BG_SELECTED,
            border_radius=4,
            visible=False,
        )
        self.list_view = ft.ListView(spacing=4, padding=4, expand=True)

        super().__init__(
            content=ft.Column([self.title, self.session_bar, self.list_view], spacing=6, expand=True),
            padding=8,
            bgcolor=theme.BG_PANEL,
            border=ft.Border.all(1, theme.BORDER),
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
        done_divider_emitted = False
        for i, todo in enumerate(self.state.todos):
            if todo.status == "done" and not done_divider_emitted:
                self.list_view.controls.append(
                    ft.Container(
                        content=ft.Text("── done ──", color=theme.TEXT_DIM, size=11),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    )
                )
                done_divider_emitted = True
            is_selected = (i == self.state.todo_idx)
            self.list_view.controls.append(
                build_todo_row(
                    todo,
                    selected=is_selected,
                    is_focus=(todo.id == focus_id),
                    on_click=self.on_todo_select,
                )
            )
            if is_selected:
                expansion = self._build_expansion(todo)
                if expansion is not None:
                    self.list_view.controls.append(expansion)

    def _build_expansion(self, todo: db.Todo) -> ft.Control | None:
        try:
            notes = db.note_list_for_todo(self.state.db_path, todo.id)
        except Exception:
            notes = []
        linked_logs = [e for e in self.state.log_entries if getattr(e, "todo_id", None) == todo.id]
        if not notes and not linked_logs:
            return None

        children: list[ft.Control] = []
        if linked_logs:
            children.append(ft.Text("Log", color=theme.TEXT_DIM, size=10, weight="bold"))
            for e in linked_logs[:5]:
                first = e.content.split("\n", 1)[0][:80]
                children.append(
                    ft.Text(
                        f"  [{e.tag_key}]  {first}  ·  {e.created_at[:16]}",
                        color=theme.TEXT_PRIMARY, size=11, max_lines=1, overflow="ellipsis",
                    )
                )
        if notes:
            if children:
                children.append(ft.Container(height=2))
            children.append(ft.Text("Notes", color=theme.TEXT_DIM, size=10, weight="bold"))
            for n in notes[-8:]:
                content = (n.content or "")[:120]
                children.append(
                    ft.Text(
                        f"  • {content}  ·  {n.created_at[:16]}",
                        color=theme.TEXT_SECONDARY, size=11, max_lines=2,
                    )
                )

        return ft.Container(
            content=ft.Column(children, spacing=2, tight=True),
            padding=ft.Padding(left=24, right=12, top=4, bottom=6),
            bgcolor=theme.BG_PANEL,
            border=ft.Border.only(left=ft.BorderSide(2, theme.BORDER)),
        )
