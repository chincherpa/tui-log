"""Left column: filter bar, carry-over warning, log list, tag-prefixed input row."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme
from flet_app.state import AppState
from flet_app.widgets.log_entry_row import build_log_entry_row, build_date_separator


class LogPanel(ft.Container):
    """Left column container — full panel widget."""

    def __init__(
        self,
        state: AppState,
        on_entry_select: Callable[[db.LogEntry], None],
        on_log_submit: Callable[[str], None],
        on_input_focus_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.state = state
        self.on_entry_select = on_entry_select
        self.on_log_submit = on_log_submit
        self.on_input_focus_change = on_input_focus_change

        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.filter_bar = ft.Row([], spacing=8, wrap=True)
        self.carry_over = ft.Text("", color=theme.ACCENT_GOLD, size=11, visible=False)
        self.list_view = ft.ListView(spacing=2, padding=4, expand=True, auto_scroll=False)

        self.tag_chip = ft.Container(
            content=ft.Text("", color=theme.TEXT_PRIMARY, size=12, weight="bold"),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            bgcolor=theme.BG_PANEL,
            border_radius=4,
        )
        self.input = ft.TextField(
            hint_text="Eintrag… (Shift+Tab = Tag wechseln)",
            border_color=theme.BORDER,
            focused_border_color=theme.ACCENT_BLUE,
            text_size=13,
            content_padding=8,
            expand=True,
            on_submit=self._handle_submit,
            on_focus=lambda _e: self.on_input_focus_change and self.on_input_focus_change(True),
            on_blur=lambda _e: self.on_input_focus_change and self.on_input_focus_change(False),
        )
        input_row = ft.Row([self.tag_chip, self.input], spacing=6)

        super().__init__(
            content=ft.Column(
                [self.title, self.filter_bar, self.carry_over, self.list_view, input_row],
                spacing=6,
                expand=True,
            ),
            padding=8,
            bgcolor=theme.BG_PANEL,
            border=ft.border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def focus_input(self) -> None:
        self.input.focus()

    def render(self) -> None:
        self._render_title()
        self._render_filter_bar()
        self._render_carry_over()
        self._render_list()
        self._render_tag_chip()
        self.update()

    def _render_title(self) -> None:
        now = datetime.now()
        today = date.today().isoformat()
        today_count = sum(1 for e in self.state.log_entries if e.date == today)
        self.title.value = f"  📋 LOG  ·  {now.strftime('%a, %d. %b')}  ·  {today_count} Einträge heute"

    def _render_filter_bar(self) -> None:
        chips: list[ft.Control] = []
        for key in self.state.filter_keys:
            if key is None:
                label, color = "Alle", theme.ACCENT_BLUE
            else:
                tag = self.state.tags.get(key)
                label = f"{tag.symbol} {tag.key}" if tag else key
                color = tag.color if tag else theme.TEXT_SECONDARY
            active = self.state.log_filter == key
            chips.append(
                ft.Container(
                    content=ft.Text(label, color="#000000" if active else color, size=11, weight="bold"),
                    bgcolor=color if active else None,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    border_radius=10,
                )
            )
        self.filter_bar.controls = chips

    def _render_carry_over(self) -> None:
        if self.state.carry_over:
            items = [e.content[:48] for e in self.state.carry_over[:3]]
            self.carry_over.value = "  ↩  " + "  ·  ".join(items)
            self.carry_over.visible = True
        else:
            self.carry_over.visible = False

    def _render_list(self) -> None:
        entries = self.state.filtered_entries()
        self.list_view.controls.clear()
        if not entries:
            self.list_view.controls.append(
                ft.Text("  (noch keine Einträge)", color=theme.TEXT_DIM, italic=True)
            )
            return
        today = date.today().isoformat()
        current_date = None
        for e in entries:
            if e.date != current_date:
                current_date = e.date
                if e.date == today:
                    label = "Heute"
                else:
                    try:
                        label = date.fromisoformat(e.date).strftime("%a, %d. %b %Y")
                    except ValueError:
                        label = e.date
                self.list_view.controls.append(build_date_separator(label))
            selected = (e.id == self.state.displayed_entry_id)
            self.list_view.controls.append(
                build_log_entry_row(e, self.state.tags, selected=selected, on_click=self._handle_click)
            )

    def _render_tag_chip(self) -> None:
        if not self.state.work_tags:
            return
        tag = self.state.work_tags[self.state.tag_idx]
        self.tag_chip.content = ft.Text(
            f"{tag.symbol} {tag.key}", color=tag.color, size=12, weight="bold"
        )

    def _handle_click(self, entry: db.LogEntry) -> None:
        self.on_entry_select(entry)

    def _handle_submit(self, _e: ft.ControlEvent) -> None:
        text = self.input.value.strip() if self.input.value else ""
        if not text:
            return
        self.input.value = ""
        self.on_log_submit(text)
