"""Focus session dialog: live elapsed timer, preset selector, notes input.

Returns via callback:
  - {"action": "minimize"}                     — keep session running, hide dialog
  - {"action": "stop", "outcome": str,
     "elapsed_s": int, "notes": list[str]}     — end session, hand off to debriefing
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme

TIMER_PRESETS = [25, 45, 90, 0]
PRESET_LABELS = ["25 min", "45 min", "90 min", "Offen"]


def show_focus(
    page: ft.Page,
    todo: db.Todo,
    started_at: str,
    on_done: Callable[[dict], None],
) -> None:
    state = {
        "preset_idx": 1,
        "notes": [],
        "stopped": False,
    }
    started_dt = datetime.fromisoformat(started_at)

    title = ft.Text(f"Focus  ·  {todo.title[:40]}", color=theme.TEXT_PRIMARY, weight="bold", size=14)
    timer_label = ft.Text("", color=theme.STATUS_COLORS["active"], size=24, weight="bold")
    preset_label = ft.Text(PRESET_LABELS[state["preset_idx"]], color=theme.TEXT_SECONDARY, size=12)
    note_input = ft.TextField(
        hint_text="Notiz hinzufügen (Enter = speichern)",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
        on_submit=lambda _e: _add_note(),
    )
    notes_view = ft.Column([], spacing=2, scroll="auto", height=120)

    def _add_note() -> None:
        text = (note_input.value or "").strip()
        if not text:
            return
        state["notes"].append(text)
        notes_view.controls.append(ft.Text(f"• {text}", color=theme.TEXT_DIM, size=12))
        note_input.value = ""
        page.update()

    def _cycle_preset(_e=None) -> None:
        state["preset_idx"] = (state["preset_idx"] + 1) % len(TIMER_PRESETS)
        preset_label.value = PRESET_LABELS[state["preset_idx"]]
        page.update()

    def _elapsed_s() -> int:
        return int((datetime.now() - started_dt).total_seconds())

    def _fmt(elapsed: int) -> str:
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _tick() -> None:
        while not state["stopped"]:
            elapsed = _elapsed_s()
            timer_label.value = _fmt(elapsed)
            try:
                page.update()
            except Exception:
                break
            threading.Event().wait(1)

    def _close_with(payload: dict) -> None:
        state["stopped"] = True
        page.pop_dialog()
        on_done(payload)

    def _minimize(_e=None) -> None:
        _close_with({"action": "minimize"})

    def _stop(outcome: str) -> None:
        _close_with({
            "action": "stop",
            "outcome": outcome,
            "elapsed_s": _elapsed_s(),
            "notes": state["notes"],
        })

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=title,
        content=ft.Column(
            [
                ft.Row([timer_label, preset_label,
                        ft.IconButton(ft.Icons.TIMER, tooltip="Preset wechseln", on_click=_cycle_preset)],
                       alignment="center", vertical_alignment="center", spacing=12),
                ft.Divider(color=theme.BORDER),
                note_input,
                notes_view,
            ],
            width=520, spacing=10, tight=True,
        ),
        actions=[
            ft.TextButton("Minimieren (Esc)", on_click=_minimize),
            ft.OutlinedButton("Blockiert", on_click=lambda _e: _stop("blocked")),
            ft.OutlinedButton("Weiter offen", on_click=lambda _e: _stop("open")),
            ft.FilledButton("Gelöst", on_click=lambda _e: _stop("solved"),
                            style=ft.ButtonStyle(bgcolor=theme.STATUS_COLORS["active"], color="#000000")),
        ],
        actions_alignment="end",
    )
    page.show_dialog(dlg)
    threading.Thread(target=_tick, daemon=True).start()
