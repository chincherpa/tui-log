"""Weekly review dialog — overlay summary of last 7 days."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import flet as ft

from tui_log import db_utils as db

from flet_app import theme


def _fmt_duration(seconds: int) -> str:
    if seconds == 0:
        return "–"
    m = seconds // 60
    h = m // 60
    rm = m % 60
    if h == 0:
        return f"{m}m"
    return f"{h}h {rm:02d}m"


def _energy_dots(value: float | None) -> str:
    if value is None:
        return "–"
    filled = round(value)
    return "●" * filled + "○" * (5 - filled) + f"  {value:.1f}/5"


def show_weekly(page: ft.Page, db_path: Path) -> None:
    state = {"offset": 0}
    body = ft.Column([], spacing=8, width=560, height=480, scroll="auto", tight=True)

    def _render() -> None:
        today = date.today()
        monday = today - timedelta(days=today.weekday() + 7 * state["offset"])
        sunday = monday + timedelta(days=6)
        iso_week = f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}"

        meta = db.day_meta_range(db_path, monday.isoformat(), sunday.isoformat()) \
            if hasattr(db, "day_meta_range") else []
        sessions = db.session_get_range(db_path, monday.isoformat(), sunday.isoformat()) \
            if hasattr(db, "session_get_range") else []
        todos = db.todo_list(db_path, mode="work")

        total_focus_s = sum(getattr(s, "duration_s", 0) for s in sessions)
        done = [t for t in todos if t.status == "done" and t.done_at and monday.isoformat() <= t.done_at[:10] <= sunday.isoformat()]
        open_now = [t for t in todos if t.status in ("open", "active", "paused")]

        energies = [m.morning_energy for m in meta if m.morning_energy is not None] if meta else []
        avg_energy = sum(energies) / len(energies) if energies else None

        body.controls = [
            ft.Text(f"KW {monday.isocalendar()[1]}  ·  {monday.strftime('%d. %b')} – {sunday.strftime('%d. %b %Y')}",
                    color=theme.TEXT_PRIMARY, size=14, weight="bold"),
            ft.Divider(color=theme.BORDER),
            ft.Text("ARBEIT", color=theme.ACCENT_BLUE, weight="bold"),
            ft.Text(f"Ø Energie  {_energy_dots(avg_energy)}", color=theme.TEXT_PRIMARY),
            ft.Text(f"{len(done)} done  ·  {len(open_now)} offen", color=theme.TEXT_PRIMARY),
            ft.Text(f"Fokus-Zeit:  {_fmt_duration(total_focus_s)}", color=theme.TEXT_PRIMARY),
            ft.Divider(color=theme.BORDER),
            ft.Text("DONE THIS WEEK", color=theme.STATUS_COLORS["done"], weight="bold"),
            *([ft.Text(f"  ✓  {t.title}", color=theme.TEXT_PRIMARY, size=12) for t in done] or
            [ft.Text("  (keine erledigten Todos)", color=theme.TEXT_DIM, italic=True)]),
        ]
        page.update()

    def _prev(_e=None) -> None:
        state["offset"] += 1
        _render()

    def _next(_e=None) -> None:
        if state["offset"] > 0:
            state["offset"] -= 1
            _render()

    def _close(_e=None) -> None:
        page.close(dlg)

    dlg = ft.AlertDialog(
        modal=True, bgcolor=theme.BG_PANEL,
        title=ft.Text("Wochenrückblick", color=theme.TEXT_SECONDARY),
        content=body,
        actions=[
            ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Vorwoche", on_click=_prev),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Nächste", on_click=_next),
            ft.FilledButton("Schließen", on_click=_close),
        ],
        actions_alignment="end",
    )
    page.open(dlg)
    _render()
