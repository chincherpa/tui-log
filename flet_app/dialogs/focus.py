"""Focus session dialog: live elapsed timer, preset selector, notes input.

Returns via callback:
  - {"action": "minimize"}                     — keep session running, hide dialog
  - {"action": "stop", "outcome": str,
     "elapsed_s": int, "notes": list[str]}     — end session, hand off to debriefing
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Callable

import flet as ft

from tui_log import db_utils as db

from flet_app import theme



def show_focus(
    page: ft.Page,
    todo: db.Todo,
    started_at: str,
    on_done: Callable[[dict], None],
    *,
    db_path=None,
    app=None,
) -> None:
    state = {
        "notes": [],
        "stopped": False,
        "paused": False,
        "accumulated_s": 0,
        "period_start": None,  # set after fromisoformat
    }
    started_dt = datetime.fromisoformat(started_at)
    state["period_start"] = started_dt

    title = ft.Text(f"Focus  ·  {todo.title[:40]}", color=theme.TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=14)
    timer_label = ft.Text("", color=theme.STATUS_COLORS["active"], size=24, weight=ft.FontWeight.BOLD)
    pause_btn = ft.OutlinedButton("⏸  Pause", on_click=lambda _e: _toggle_pause())

    # ── Sub-Todos ─────────────────────────────────────────────────
    subtodos_col = ft.Column([], spacing=3)

    def _build_subtodo_row(st: db.SubTodo) -> ft.Control:
        check_icon = "✓" if st.done else "○"
        check_color = theme.STATUS_COLORS["done"] if st.done else theme.TEXT_DIM
        title_color = theme.TEXT_DIM if st.done else theme.TEXT_PRIMARY
        title_style = ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if st.done else None

        def _on_toggle(_e, subtodo_id=st.id) -> None:
            if db_path is not None:
                db.subtodo_toggle(db_path, subtodo_id)
                _reload_subtodos()

        return ft.GestureDetector(
            on_tap=_on_toggle,
            content=ft.Container(
                content=ft.Row(
                    [  # type: ignore[arg-type]
                        ft.Text(check_icon, color=check_color, size=13, width=18),
                        ft.Text(
                            st.title,
                            color=title_color,
                            size=13,
                            style=title_style,
                            expand=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=4, right=4, top=3, bottom=3),
                border_radius=4,
            ),
            mouse_cursor=ft.MouseCursor.CLICK,
        )

    def _reload_subtodos() -> None:
        if db_path is None:
            return
        subtodos = db.subtodo_list_for_todo(db_path, todo.id)
        subtodos_col.controls.clear()
        for st in subtodos:
            subtodos_col.controls.append(_build_subtodo_row(st))
        page.update()

    _reload_subtodos()

    subtodo_input = ft.TextField(  # type: ignore[call-arg]
        hint_text="Sub-Todo hinzufügen...",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=12,
        height=36,
        content_padding=ft.Padding(left=8, right=8, top=4, bottom=4),
        on_submit=lambda _e: _add_subtodo(),  # type: ignore[call-arg]
    )

    def _add_subtodo() -> None:
        title = (subtodo_input.value or "").strip()
        if not title or db_path is None:
            return
        db.subtodo_add(db_path, todo.id, title)
        subtodo_input.value = ""
        _reload_subtodos()

    # ── Notes ──────────────────────────────────────────────────────
    note_input = ft.TextField(  # type: ignore[call-arg]
        hint_text="Notiz hinzufügen...",
        border_color=theme.BORDER,
        focused_border_color=theme.ACCENT_BLUE,
        text_size=13,
        on_submit=lambda _e: _add_note(),  # type: ignore[call-arg]
    )
    notes_view = ft.Column([], spacing=2, scroll=ft.ScrollMode.AUTO, height=120)

    def _add_note() -> None:
        text = (note_input.value or "").strip()
        if not text:
            return
        state["notes"].append(text)
        notes_view.controls.append(ft.Text(f"• {text}", color=theme.TEXT_DIM, size=12))
        note_input.value = ""
        page.update()

    def _elapsed_s() -> int:
        if state["paused"]:
            return state["accumulated_s"]
        return state["accumulated_s"] + int((datetime.now() - state["period_start"]).total_seconds())

    def _fmt(elapsed: int) -> str:
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _toggle_pause() -> None:
        if state["paused"]:
            state["period_start"] = datetime.now()
            state["paused"] = False
            timer_label.color = theme.STATUS_COLORS["active"]
            pause_btn.text = "⏸  Pause"  # type: ignore[attr-defined]
        else:
            state["accumulated_s"] = _elapsed_s()
            state["paused"] = True
            timer_label.color = theme.ACCENT_GOLD
            pause_btn.text = "▶  Weiter"  # type: ignore[attr-defined]
        try:
            timer_label.update()
            pause_btn.update()
        except Exception:
            pass

    async def _tick() -> None:
        # Brief delay so the dialog is mounted before first update
        await asyncio.sleep(0.2)
        while not state["stopped"]:
            if not state["paused"]:
                elapsed = _elapsed_s()
                timer_label.value = _fmt(elapsed)
                try:
                    timer_label.update()
                except Exception:
                    break
            await asyncio.sleep(1)

    def _close_with(payload: dict) -> None:
        state["stopped"] = True
        if app is not None:
            app.dialog_escape_handler = None
            app.dialog_pause_handler = None
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
                ft.Row([timer_label, pause_btn],
                       alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                ft.Divider(color=theme.BORDER),
                *([
                    ft.Text("Sub-Todos", color=theme.TEXT_DIM, size=10, weight=ft.FontWeight.BOLD),
                    subtodos_col,
                    subtodo_input,
                    ft.Divider(color=theme.BORDER),
                ] if db_path is not None else []),
                note_input,
                notes_view,
            ],
            width=520, spacing=10, tight=True,
        ),
        actions=[  # type: ignore[arg-type]
            ft.TextButton("Minimieren (Esc)", on_click=_minimize),
            ft.OutlinedButton("Blockiert", on_click=lambda _e: _stop("blocked")),
            ft.OutlinedButton("Weiter offen", on_click=lambda _e: _stop("open")),
            ft.FilledButton("Gelöst", on_click=lambda _e: _stop("solved"),
                            style=ft.ButtonStyle(bgcolor=theme.STATUS_COLORS["active"], color="#000000")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    if app is not None:
        app.dialog_escape_handler = lambda: _minimize()
        app.dialog_pause_handler = lambda: _toggle_pause()
    page.show_dialog(dlg)
    try:
        page.run_task(_tick)
    except Exception:
        # Fallback: schedule via threading (may still not update from thread on Flet 0.84)
        def _thread_target() -> None:
            asyncio.run(_tick())
        threading.Thread(target=_thread_target, daemon=True).start()
