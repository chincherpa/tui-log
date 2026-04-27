"""Debriefing dialog after a focus session — captures outcome + log entry."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme

OUTCOMES = ["solved", "open", "blocked"]
OUTCOME_DISPLAY = {"solved": "✓ Gelöst", "open": "↻ Weiter offen", "blocked": "✕ Blockiert"}


def _fmt_duration(seconds: int) -> str:
    m = seconds // 60
    h = m // 60
    rm = m % 60
    if h == 0:
        return f"{m} min"
    return f"{h}h {rm:02d}min"


def show_debriefing(
    page: ft.Page,
    todo_title: str,
    elapsed_s: int,
    suggested_outcome: str,
    on_done: Callable[[dict | None], None],
) -> None:
    initial = suggested_outcome if suggested_outcome in OUTCOMES else "open"
    outcome_dd = ft.Dropdown(
        label="Ergebnis",
        value=initial,
        options=[ft.dropdown.Option(o, OUTCOME_DISPLAY[o]) for o in OUTCOMES],
        border_color=theme.BORDER,
    )
    log_input = ft.TextField(
        label="Eintrag fürs Tages-Log",
        hint_text="Kurz beschreiben was passiert ist…",
        autofocus=True, multiline=True, min_lines=2, max_lines=4,
        border_color=theme.BORDER, focused_border_color=theme.ACCENT_BLUE,
    )

    def _close(payload: dict | None) -> None:
        page.pop_dialog()
        on_done(payload)

    def _save(_e=None) -> None:
        _close({"outcome": outcome_dd.value or "open", "log_entry": (log_input.value or "").strip()})

    dlg = ft.AlertDialog(
        modal=True, bgcolor=theme.BG_PANEL,
        title=ft.Text(f"Session abgeschlossen  ·  {todo_title[:40]}  ·  {_fmt_duration(elapsed_s)}",
                      color=theme.TEXT_PRIMARY, weight="bold"),
        content=ft.Column([outcome_dd, log_input], spacing=10, width=480, tight=True),
        actions=[
            ft.TextButton("Ohne Eintrag", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=_save),
        ],
        actions_alignment="end",
    )
    page.show_dialog(dlg)
