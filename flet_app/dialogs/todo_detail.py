"""Todo-Detail-Dialog: Sub-Todos (Checkboxen) und Notizen verwalten.

Schreibt Änderungen sofort in die DB (kein finales "Speichern").
Ruft callback(None) beim Schließen auf – der Aufrufer lädt den State neu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import flet as ft

from tui_log import db_utils as db
from flet_app import theme


def show_todo_detail(
    page: ft.Page,
    todo: db.Todo,
    db_path: Path,
    callback: Callable[[None], None],
    *,
    app=None,
) -> None:
    # ── Sub-Todo list ──────────────────────────────────────────────────────
    subtodos_col = ft.Column([], spacing=3, scroll="auto")
    subtodo_input = ft.TextField(
        hint_text="Neues Sub-Todo (Enter)",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
        expand=True,
        on_submit=lambda _e: _add_subtodo(),
    )

    def _build_subtodo_row(st: db.SubTodo) -> ft.Control:
        check_icon = "✓" if st.done else "○"
        check_color = theme.STATUS_COLORS["done"] if st.done else theme.TEXT_DIM
        title_color = theme.TEXT_DIM if st.done else theme.TEXT_PRIMARY
        title_style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if st.done else None

        def _on_toggle(_e, subtodo_id=st.id) -> None:
            db.subtodo_toggle(db_path, subtodo_id)
            _reload_subtodos()

        return ft.GestureDetector(
            on_tap=_on_toggle,
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Text(check_icon, color=check_color, size=13, width=18),
                        ft.Text(
                            st.title,
                            color=title_color,
                            size=13,
                            style=title_style,
                            expand=True,
                            max_lines=2,
                            overflow="ellipsis",
                        ),
                    ],
                    spacing=6,
                    vertical_alignment="center",
                ),
                padding=ft.Padding(left=4, right=4, top=3, bottom=3),
                border_radius=4,
            ),
            mouse_cursor=ft.MouseCursor.CLICK,
        )

    def _reload_subtodos() -> None:
        subtodos = db.subtodo_list_for_todo(db_path, todo.id)
        subtodos_col.controls.clear()
        if subtodos:
            for st in subtodos:
                subtodos_col.controls.append(_build_subtodo_row(st))
        else:
            subtodos_col.controls.append(
                ft.Text("(noch keine Sub-Todos)", color=theme.TEXT_DIM, size=12, italic=True)
            )
        page.update()

    def _add_subtodo() -> None:
        text = (subtodo_input.value or "").strip()
        if not text:
            return
        db.subtodo_add(db_path, todo.id, text)
        subtodo_input.value = ""
        _reload_subtodos()

    # ── Notes list ────────────────────────────────────────────────────────
    notes_col = ft.Column([], spacing=3, scroll="auto")
    note_input = ft.TextField(
        hint_text="Neue Notiz (Enter)",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
        expand=True,
        on_submit=lambda _e: _add_note(),
    )

    def _reload_notes() -> None:
        notes = db.note_list_for_todo(db_path, todo.id)
        notes_col.controls.clear()
        if notes:
            for n in notes[-12:]:
                notes_col.controls.append(
                    ft.Text(
                        f"  • {n.content}  ·  {n.created_at[:16]}",
                        color=theme.TEXT_SECONDARY,
                        size=12,
                        max_lines=3,
                    )
                )
        else:
            notes_col.controls.append(
                ft.Text("(noch keine Notizen)", color=theme.TEXT_DIM, size=12, italic=True)
            )
        page.update()

    def _add_note() -> None:
        text = (note_input.value or "").strip()
        if not text:
            return
        db.note_add(db_path, todo.id, text)
        note_input.value = ""
        _reload_notes()

    # ── Initial load ──────────────────────────────────────────────────────
    _reload_subtodos()
    _reload_notes()

    # ── Close ─────────────────────────────────────────────────────────────
    def _close(_e=None) -> None:
        if app is not None:
            app.dialog_escape_handler = None
        page.pop_dialog()
        callback(None)

    # ── Layout ────────────────────────────────────────────────────────────
    context_suffix = f"  ·  {todo.context}" if todo.context else ""
    title_text = ft.Text(
        f"{todo.title}{context_suffix}",
        color=theme.TEXT_PRIMARY,
        weight="bold",
        size=14,
        max_lines=2,
        overflow="ellipsis",
    )

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=title_text,
        content=ft.Column(
            [
                # Sub-Todos section
                ft.Text("Sub-Todos", color=theme.TEXT_DIM, size=11, weight="bold"),
                ft.Container(
                    content=subtodos_col,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=4,
                    padding=6,
                ),
                ft.Row([subtodo_input], spacing=6),
                ft.Divider(color=theme.BORDER),
                # Notes section
                ft.Text("Notizen", color=theme.TEXT_DIM, size=11, weight="bold"),
                ft.Container(
                    content=notes_col,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=4,
                    padding=6,
                ),
                ft.Row([note_input], spacing=6),
            ],
            width=540,
            spacing=8,
            tight=True,
        ),
        actions=[
            ft.FilledButton("Schließen", on_click=_close),
        ],
        actions_alignment="end",
    )

    if app is not None:
        app.dialog_escape_handler = _close

    page.show_dialog(dlg)
