"""Middle column: read-only display of the currently selected log entry."""

from __future__ import annotations

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


class ContentPanel(ft.Container):
    def __init__(self) -> None:
        self.title = ft.Text("", color=theme.TEXT_SECONDARY, size=12, weight="bold")
        self.body = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
            code_theme="atom-one-dark",
        )
        self.scroll = ft.Column([self.body], scroll="auto", expand=True)
        super().__init__(
            content=ft.Column([self.title, self.scroll], spacing=6, expand=True),
            padding=12,
            bgcolor=theme.BG_PANEL,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=6,
            expand=True,
        )

    def show_entry(self, entry: db.LogEntry | None) -> None:
        if entry is None:
            self.title.value = "  📄 CONTENT"
            self.body.value = "_(kein Eintrag ausgewählt)_"
        else:
            self.title.value = f"  📄 {entry.tag_key.upper()}  ·  {entry.created_at[:16]}"
            parts = entry.content.split("\n", 1)
            head = f"### {parts[0]}\n"
            if len(parts) > 1 and parts[1].strip():
                # Preserve single-line breaks (markdown collapses bare \n)
                tail = parts[1].replace("\n", "  \n")
                self.body.value = head + "\n---\n\n" + tail
            else:
                self.body.value = head
        self.update()
