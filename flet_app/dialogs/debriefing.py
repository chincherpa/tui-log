"""Debriefing dialog after a focus session — captures outcome + log entry."""

from __future__ import annotations

from typing import Callable

import flet as ft

from flet_app import theme

OUTCOMES = ["solved", "open", "blocked"]
OUTCOME_DISPLAY = {"solved": "✓ Gelöst", "open": "↻ Weiter offen", "blocked": "✕ Blockiert"}
OUTCOME_COLOR = {
    "solved":  theme.STATUS_COLORS["active"],
    "open":    theme.ACCENT_GOLD,
    "blocked": theme.ACCENT_RED,
}


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
    selected = {"value": initial}

    outcome_label = ft.Text("Ergebnis", color=theme.TEXT_SECONDARY, size=12)
    outcome_row = ft.Row([], spacing=6)

    def _build_outcome_row() -> None:
        chips: list[ft.Control] = []
        for o in OUTCOMES:
            active = (selected["value"] == o)
            color = OUTCOME_COLOR[o]
            chips.append(
                ft.Container(
                    content=ft.Text(
                        OUTCOME_DISPLAY[o],
                        color="#000000" if active else color,
                        weight="bold", size=13,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    bgcolor=color if active else theme.BG_SELECTED,
                    border=ft.Border.all(1, color),
                    border_radius=6,
                    on_click=lambda _e, k=o: _pick(k),
                )
            )
        outcome_row.controls = chips

    def _pick(o: str) -> None:
        selected["value"] = o
        _build_outcome_row()
        try:
            outcome_row.update()
        except Exception:
            pass

    _build_outcome_row()

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
        _close({
            "outcome": selected["value"],
            "log_entry": (log_input.value or "").strip(),
        })

    dlg = ft.AlertDialog(
        modal=True, bgcolor=theme.BG_PANEL,
        title=ft.Text(f"Session abgeschlossen  ·  {todo_title[:40]}  ·  {_fmt_duration(elapsed_s)}",
                      color=theme.TEXT_PRIMARY, weight="bold"),
        content=ft.Column(
            [outcome_label, outcome_row, log_input],
            spacing=10, width=480, tight=True,
        ),
        actions=[
            ft.TextButton("Ohne Eintrag", on_click=lambda _e: _close(None)),
            ft.FilledButton("Speichern", on_click=_save),
        ],
        actions_alignment="end",
    )
    page.show_dialog(dlg)
