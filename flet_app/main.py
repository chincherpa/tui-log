"""Main Flet app — wires panels, state, dialogs, keybindings, live timer."""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime
from pathlib import Path

import flet as ft

from tui_log import db_utils as db
from tui_log.config import AppConfig

from flet_app import theme
from flet_app.state import AppState
from flet_app.panels.log_panel import LogPanel
from flet_app.panels.content_panel import ContentPanel
from flet_app.panels.todo_panel import TodoPanel
from flet_app.dialogs.confirm import show_confirm
from flet_app.dialogs.new_todo import show_new_todo
from flet_app.dialogs.tag_select import show_tag_select
from flet_app.dialogs.content_edit import show_content_edit
from flet_app.dialogs.focus import show_focus
from flet_app.dialogs.debriefing import show_debriefing
from flet_app.dialogs.weekly import show_weekly
from flet_app.git_push import trigger_git_push
from flet_app.widgets.toast import show_toast
from flet_app import keybindings


PANEL_ORDER = ["log", "content", "todo"]


class WorkApp:
    def __init__(self, page: ft.Page, cfg: AppConfig) -> None:
        self.page = page
        self.cfg = cfg

        work_tags = cfg.tags.by_category("work") + cfg.tags.by_category("any")
        self.state = AppState(db_path=cfg.db_path, tags=cfg.tags, work_tags=work_tags)
        self.state.load_all()

        self.log_panel = LogPanel(
            self.state,
            on_entry_select=self._on_entry_select,
            on_log_submit=self._on_log_submit,
            on_input_focus_change=self._on_input_focus_change,
        )
        self.content_panel = ContentPanel()
        self.todo_panel = TodoPanel(self.state, on_todo_select=self._on_todo_select)

        self.last_action_was_filter = False
        self.input_focused = False
        self._panel_idx = 0
        self._stop_clock = False

        self.state.on_change = self._refresh_all_panels

    # ── lifecycle ─────────────────────────────────────────────────────────

    def setup_page(self) -> None:
        self.page.title = "tui-log — daily journal"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = theme.BG_BASE
        self.page.padding = 8
        self.page.window.width = 1400
        self.page.window.height = 900
        self.page.window.min_width = 900
        self.page.window.min_height = 600
        self.page.window.center()

        self.page.add(
            ft.Row(
                [self.log_panel, self.content_panel, self.todo_panel],
                expand=True, spacing=8,
            )
        )
        self._refresh_all_panels()
        self._show_displayed_entry()

        keybindings.attach(self.page, self)
        self._start_clock()

    # ── refresh ───────────────────────────────────────────────────────────

    def _refresh_all_panels(self) -> None:
        self.log_panel.render()
        self.todo_panel.render()
        self._show_displayed_entry()

    def _show_displayed_entry(self) -> None:
        entry = None
        if self.state.displayed_entry_id is not None:
            entry = next((e for e in self.state.log_entries if e.id == self.state.displayed_entry_id), None)
        self.content_panel.show_entry(entry)

    # ── live clock for active session ─────────────────────────────────────

    def _start_clock(self) -> None:
        def _tick() -> None:
            while not self._stop_clock:
                if self.state.active_session:
                    started = datetime.fromisoformat(self.state.active_session.started_at)
                    elapsed = self.state.active_session_base_s + int((datetime.now() - started).total_seconds())
                    h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
                    timer = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                    label = f"  ▶  {self.state.active_session_title}  ·  {timer}"
                    try:
                        self.todo_panel.update_session_timer(label)
                    except Exception:
                        break
                else:
                    try:
                        self.todo_panel.update_session_timer(None)
                    except Exception:
                        break
                threading.Event().wait(1)

        threading.Thread(target=_tick, daemon=True).start()

    # ── selection callbacks ───────────────────────────────────────────────

    def _on_entry_select(self, entry: db.LogEntry) -> None:
        self.state.displayed_entry_id = entry.id
        self._show_displayed_entry()

    def _on_input_focus_change(self, has_focus: bool) -> None:
        self.input_focused = has_focus

    def _on_todo_select(self, todo: db.Todo) -> None:
        ids = [t.id for t in self.state.todos]
        if todo.id in ids:
            self.state.todo_idx = ids.index(todo.id)
            self.todo_panel.render()

    def _on_log_submit(self, text: str) -> None:
        if not self.state.work_tags:
            return
        tag_key = self.state.work_tags[self.state.tag_idx].key
        db.log_add(self.state.db_path, tag_key=tag_key, content=text, mode="work")
        self.state.load_log()
        self._refresh_all_panels()

    # ── actions ───────────────────────────────────────────────────────────

    def action_focus_log_input(self) -> None:
        self.log_panel.focus_input()
        self.last_action_was_filter = False

    def action_next_tag(self) -> None:
        self.state.cycle_tag(1)
        self.log_panel.render()

    def action_prev_tag(self) -> None:
        self.state.cycle_tag(-1)
        self.log_panel.render()

    def action_next_filter(self) -> None:
        self.state.cycle_filter(1)
        self.log_panel.render()
        self.last_action_was_filter = True

    def action_prev_filter(self) -> None:
        self.state.cycle_filter(-1)
        self.log_panel.render()
        self.last_action_was_filter = True

    def action_view_latest(self) -> None:
        if self.state.log_entries:
            self.state.displayed_entry_id = self.state.log_entries[0].id
            self._show_displayed_entry()

    def action_refresh_all(self) -> None:
        self.state.load_all()
        self._refresh_all_panels()
        show_toast(self.page, "Aktualisiert.")

    def action_toggle_todos(self) -> None:
        self.todo_panel.visible = not self.todo_panel.visible
        self.todo_panel.update()

    def action_toggle_content(self) -> None:
        self.content_panel.visible = not self.content_panel.visible
        self.content_panel.update()

    def action_cycle_panel(self, direction: int = 1) -> None:
        self._panel_idx = (self._panel_idx + direction) % len(PANEL_ORDER)
        target = PANEL_ORDER[self._panel_idx]
        if target == "log":
            self.log_panel.focus_input()

    def action_todo_up(self) -> None:
        if self.state.todos and self.state.todo_idx > 0:
            self.state.todo_idx -= 1
            self.todo_panel.render()

    def action_todo_down(self) -> None:
        if self.state.todos and self.state.todo_idx < len(self.state.todos) - 1:
            self.state.todo_idx += 1
            self.todo_panel.render()

    def action_todo_activate(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status in ("open", "paused"):
            db.todo_set_status(self.state.db_path, todo.id, "active")
            show_toast(self.page, f"▶  {todo.title[:40]}")
        elif todo.status == "active":
            db.todo_set_status(self.state.db_path, todo.id, "paused")
            show_toast(self.page, f"‖  {todo.title[:40]} pausiert")
        self.state.load_todos()
        self.todo_panel.render()

    def action_todo_done(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status == "done":
            return
        if self.state.active_session and self.state.active_session.todo_id == todo.id:
            db.session_end(self.state.db_path, self.state.active_session.id, outcome="solved", log_entry="")
            self.state.check_active_session()
        db.todo_set_status(self.state.db_path, todo.id, "done")
        db.log_add(self.state.db_path, tag_key="done", content=todo.title, mode="work")
        self.state.load_todos()
        self.state.load_log()
        self._refresh_all_panels()
        show_toast(self.page, f"✓  {todo.title[:40]}", severity="success")

    def action_todo_delete(self) -> None:
        if not self.state.todos:
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status == "cancelled":
            return

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            if self.state.active_session and self.state.active_session.todo_id == todo.id:
                db.session_end(self.state.db_path, self.state.active_session.id, outcome="open", log_entry="")
                self.state.check_active_session()
            db.todo_set_status(self.state.db_path, todo.id, "cancelled")
            self.state.load_todos()
            self.todo_panel.render()
            show_toast(self.page, f"✗  '{todo.title[:40]}' cancelled")

        show_confirm(self.page, f"'{todo.title[:50]}' wirklich canceln?", _on_confirm)

    def action_add_todo(self) -> None:
        prefill = self.log_panel.input.value or ""

        def _on_save(payload: dict | None) -> None:
            if not payload:
                return
            db.todo_add(
                self.state.db_path,
                title=payload["title"], context=payload["context"],
                priority=payload["priority"], mode=payload["mode"],
            )
            if prefill:
                self.log_panel.input.value = ""
            self.state.load_todos()
            self._refresh_all_panels()
            show_toast(self.page, f"Todo angelegt: {payload['title'][:40]}", severity="success")

        show_new_todo(self.page, _on_save, prefill_title=prefill)

    def action_edit_entry(self) -> None:
        if not self.state.displayed_entry_id:
            show_toast(self.page, "Kein Eintrag ausgewählt")
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return

        def _on_save(content: str | None) -> None:
            if content is None:
                return
            try:
                db.log_update(self.state.db_path, entry.id, content=content)
                self.state.load_log()
                self._refresh_all_panels()
                show_toast(self.page, "Eintrag gespeichert", severity="success")
            except Exception as e:
                logging.error(f"edit_entry failed:\n{traceback.format_exc()}")
                show_toast(self.page, f"Fehler: {e}", severity="error", duration_ms=4000)

        show_content_edit(self.page, entry.content, _on_save)

    def action_change_tag(self) -> None:
        if not self.state.displayed_entry_id:
            show_toast(self.page, "Kein Eintrag ausgewählt")
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return

        def _on_select(new_key: str | None) -> None:
            if new_key is None or new_key == entry.tag_key:
                return
            db.log_update(self.state.db_path, entry.id, tag_key=new_key)
            self.state.load_log()
            self._refresh_all_panels()
            show_toast(self.page, f"Tag → {new_key}", severity="success")

        show_tag_select(self.page, self.state.tags, entry.tag_key, _on_select)

    def action_delete_entry(self) -> None:
        if not self.state.displayed_entry_id:
            return
        entry = db.log_get(self.state.db_path, self.state.displayed_entry_id)
        if not entry:
            return
        preview = entry.content.split("\n", 1)[0][:50]

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            db.log_delete(self.state.db_path, entry.id)
            self.state.displayed_entry_id = None
            self.state.load_log()
            self._refresh_all_panels()
            show_toast(self.page, "Eintrag gelöscht")

        show_confirm(self.page, f"Eintrag löschen: '{preview}'?", _on_confirm)

    def action_open_weekly(self) -> None:
        show_weekly(self.page, self.state.db_path)

    def action_git_push_db(self) -> None:
        trigger_git_push(self.page, self.state.db_path)

    def action_start_focus(self) -> None:
        if not self.state.todos:
            show_toast(self.page, "Keine offenen Todos.", severity="warning")
            return
        todo = self.state.todos[self.state.todo_idx]
        if todo.status not in ("open", "paused", "active"):
            candidates = [t for t in self.state.todos if t.status in ("open", "paused", "active")]
            if not candidates:
                show_toast(self.page, "Keine offenen Todos.", severity="warning")
                return
            todo = candidates[0]

        existing = db.session_get_active(self.state.db_path)
        if existing:
            if existing.todo_id == todo.id:
                db.session_end(self.state.db_path, existing.id, outcome="open", log_entry="")
                self.state.check_active_session()
                self.state.load_todos()
                self._refresh_all_panels()
                show_toast(self.page, f"Focus beendet: {todo.title[:40]}")
                return
            db.session_end(self.state.db_path, existing.id, outcome="open", log_entry="")

        session = db.session_start(self.state.db_path, todo.id)
        self.state.check_active_session()
        self._refresh_all_panels()

        def _on_focus_done(payload: dict) -> None:
            if payload.get("action") == "minimize":
                return

            def _on_debrief(debrief: dict | None) -> None:
                try:
                    if debrief is None:
                        db.session_end(self.state.db_path, session.id,
                                       outcome=payload["outcome"], log_entry="")
                    else:
                        db.session_end(self.state.db_path, session.id,
                                       outcome=debrief["outcome"], log_entry=debrief["log_entry"])
                        if debrief["log_entry"]:
                            tag_key = "done" if debrief["outcome"] == "solved" else "block"
                            db.log_add(self.state.db_path, tag_key=tag_key,
                                       content=debrief["log_entry"], mode="work", todo_id=todo.id)
                        for note in payload.get("notes", []):
                            db.note_add(self.state.db_path, todo.id, note, session_id=session.id)
                    self.state.check_active_session()
                    self.state.load_all()
                    self._refresh_all_panels()
                except Exception as e:
                    logging.error(f"on_debrief failed:\n{traceback.format_exc()}")
                    show_toast(self.page, f"Fehler: {e}", severity="error", duration_ms=4000)

            show_debriefing(self.page, todo.title, payload["elapsed_s"], payload["outcome"], _on_debrief)

        show_focus(self.page, todo, session.started_at, _on_focus_done)


# ── entry point ───────────────────────────────────────────────────────────

def run(cfg: AppConfig) -> None:
    def _target(page: ft.Page) -> None:
        app = WorkApp(page, cfg)
        app.setup_page()

    ft.app(target=_target)
