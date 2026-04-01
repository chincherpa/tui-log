"""
tui_log/work_app.py
~~~~~~~~~~~~~~~~~~~
Work-Modus TUI – Haupt-App.

Layout:
  ┌─ Header: Modus · Datum · Uhrzeit · Fokus ──────────────────┐
  │  LOG-PANEL (links 2/3)   │  TODO-PANEL (rechts 1/3)        │
  │  carry-over Warnung      │  aktive Session Badge            │
  │  morgen-Bar              │  Todo-Liste                      │
  │  Log-Einträge            │                                  │
  │  [Tag] Eingabe-Leiste    │                                  │
  ├─ Footer: Keybindings ──────────────────────────────────────┤

Keybindings:
  SPACE / n   → Fokus auf Log-Eingabe
  f           → Focus-Session starten (markiertes Todo)
  t           → Todo-Panel toggle
  a           → Neues Todo anlegen
  /           → Suche (TODO: nächste Iteration)
  r           → Refresh
  q           → Beenden
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import (
    Footer, Header, Input, Label, ListItem, ListView, Static
)
from textual import on, work

from rich.markup import escape

from .config import AppConfig
from .mode import detect_mode, Mode
from . import db_utils as db
from .widgets.morning import MorningModal
from .widgets.focus import FocusModal
from .widgets.debriefing import DebriefingModal
from .widgets.log_input import LogInput
from .widgets.new_todo import NewTodoModal


# ── Tag-Hilfsfunktionen ───────────────────────────────────────────────────────

def _tag_markup(tag_key: str, tags) -> str:
    """Gibt Rich-Markup für ein Tag zurück."""
    tag = tags.get(tag_key)
    if tag:
        return f"[bold {tag.color}]{tag.symbol} {tag.key}[/]"
    return f"[dim]{tag_key}[/]"


def _fmt_time(iso_dt: str) -> str:
    """'2026-03-31 09:14:32' → '09:14'"""
    try:
        return iso_dt[11:16]
    except Exception:
        return "??:??"


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m = seconds // 60
    h = m // 60
    if h == 0:
        return f"{m}m"
    return f"{h}h{m % 60:02d}"


# ── Log-Eintrag Widget ────────────────────────────────────────────────────────

class LogEntryWidget(Static):
    """Eine Zeile im Log."""

    def __init__(self, entry: db.LogEntry, tags) -> None:
        tag = tags.get(entry.tag_key)
        symbol = tag.symbol if tag else "·"
        color  = tag.color  if tag else "#888888"
        time_s = _fmt_time(entry.created_at)
        tag_s  = f"{symbol} {entry.tag_key:<6}"
        content = entry.content

        markup = (
            f"[dim]{time_s}[/]  "
            f"[bold {color}]{tag_s}[/]  "
            f"{content}"
        )
        super().__init__(markup, classes="log-entry")
        self.entry = entry


# ── Todo-Eintrag Widget ───────────────────────────────────────────────────────

STATUS_ICONS = {
    "open":    "[dim]○[/]",
    "active":  "[bold green]▶[/]",
    "paused":  "[dim]‖[/]",
    "done":    "[dim]✓[/]",
    "dropped": "[dim]✗[/]",
}

PRIORITY_COLORS = {
    "high":   "#FF6B6B",
    "normal": "#C8C8C8",
    "low":    "#555577",
}


class TodoItemWidget(Static):
    """Zwei-Zeilen Todo-Eintrag."""

    def __init__(self, todo: db.Todo) -> None:
        icon     = STATUS_ICONS.get(todo.status, "○")
        p_color  = PRIORITY_COLORS.get(todo.priority, "#C8C8C8")
        title_s  = todo.title[:42]
        ctx_s    = (todo.context or "")[:28]
        dur_s    = _fmt_duration(todo.total_duration_s) if todo.total_duration_s else ""
        sess_s   = f"{todo.total_sessions}×" if todo.total_sessions else ""
        stats_s  = f"{sess_s} {dur_s}".strip()

        dim_title = todo.status in ("done", "dropped")
        title_color = "#444466" if dim_title else p_color

        line1 = f"{icon} [bold {title_color}]{title_s}[/]"
        line2 = f"   [dim]{ctx_s}[/dim]" + (f"  [dim]{stats_s}[/]" if stats_s else "")

        markup = f"{line1}\n{line2}"
        super().__init__(markup, classes="todo-item")
        self.todo = todo



# ── Bestätigungs-Modal ────────────────────────────────────────────────────────

class _ConfirmModal(ModalScreen[bool]):
    """Einfaches Ja/Nein-Modal. Gibt True bei Bestätigung zurück."""

    BINDINGS = [
        Binding("y,enter", "confirm", "Ja"),
        Binding("n,escape", "cancel", "Nein"),
    ]

    DEFAULT_CSS = """
    _ConfirmModal { align: center middle; }
    #confirm-dialog {
        background: #1A0A0A;
        border: solid #FF6B6B;
        width: 52;
        height: auto;
        padding: 1 2;
    }
    #confirm-text { color: #E8E8E8; height: 1; margin-bottom: 1; }
    #confirm-hint { color: #555577; height: 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        with Vertical(id="confirm-dialog"):
            yield Label(self._message, id="confirm-text")
            yield Label("[y / Enter] Ja    [n / Esc] Nein", id="confirm-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ── Haupt-App ─────────────────────────────────────────────────────────────────

class WorkApp(App):

    CSS_PATH = "work.tcss"

    BINDINGS = [
        Binding("space,n",    "focus_log_input",  "Log",         show=True),
        Binding("f",          "start_focus",      "Focus",       show=True),
        Binding("a",          "add_todo",         "Neu Todo",    show=True),
        Binding("t",          "toggle_todos",     "Todos",       show=True),
        Binding("tab",        "next_tag",         "Tag",         show=False),
        Binding("up,k",       "todo_up",          "Todo ↑",      show=False),
        Binding("down,j",     "todo_down",        "Todo ↓",      show=False),
        Binding("enter",      "todo_activate",    "Aktivieren",  show=False),
        Binding("d",          "todo_done",        "✓ Done",      show=False),
        Binding("x",          "todo_delete",      "✗ Löschen",   show=False),
        Binding("shift+tab",  "prev_tag",         "Tag",         show=False),
        Binding("r",          "refresh_all",      "Refresh",     show=False),
        Binding("ctrl+a",     "goto_work",    "→ Arbeit",    show=True),
        Binding("ctrl+f",     "goto_family",  "→ Familie",   show=True),
        Binding("ctrl+w",     "goto_weekend", "→ Wochenende",show=True),
        Binding("q",          "quit",             "Beenden",     show=True),
    ]

    # Reaktiver State
    _tag_idx:      reactive[int]  = reactive(0)
    _todos_visible: reactive[bool] = reactive(True)
    _active_session: reactive[db.FocusSession | None] = reactive(None)
    _clock_str:    reactive[str]  = reactive("")

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.cfg          = config
        self.db_path      = config.db_path
        self.tags         = config.tags
        self._work_tags   = (
            config.tags.by_category("work") + config.tags.by_category("any")
        )
        self._log_entries: list[db.LogEntry] = []
        self._todos:       list[db.Todo]     = []
        self._carry_over:  list[db.LogEntry] = []
        self._is_mounted:  bool = False
        self._todo_idx:    int  = 0           # ausgewähltes Todo
        self._active_session_title: str = ""  # gecachter Titel der laufenden Session

    # ── Sichere UI-Helfer ─────────────────────────────────────────────────────

    def _q(self, selector: str, widget_type=None):
        """query_one das nie wirft – gibt None zurück wenn Widget nicht gefunden."""
        try:
            if widget_type:
                return self.query_one(selector, widget_type)
            return self.query_one(selector)
        except Exception:
            return None

    def _update(self, selector: str, widget_type, content: str) -> None:
        """Widget-Inhalt sicher aktualisieren."""
        w = self._q(selector, widget_type)
        if w is not None:
            try:
                w.update(content)
            except Exception:
                pass

    def _add_class(self, selector: str, css_class: str) -> None:
        w = self._q(selector)
        if w is not None:
            try:
                w.add_class(css_class)
            except Exception:
                pass

    def _remove_class(self, selector: str, css_class: str) -> None:
        w = self._q(selector)
        if w is not None:
            try:
                w.remove_class(css_class)
            except Exception:
                pass

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Horizontal(id="main-split"):
            # ── Log-Panel ─────────────────────────────────────
            with Vertical(id="log-panel"):
                yield Label("", id="log-panel-title")
                yield Label("", id="carry-over-bar")
                yield Label("", id="morning-bar")

                with ScrollableContainer(id="log-list"):
                    yield Static("", id="log-list-content")

                with Horizontal(id="log-input-row"):
                    yield Label("", id="tag-selector")
                    yield LogInput(
                        placeholder="Eintrag… (Tab = Tag wechseln)",
                        id="log-text-input",
                    )

            # ── Todo-Panel ────────────────────────────────────
            with Vertical(id="todo-panel"):
                yield Label("", id="todo-panel-title")
                yield Label("", id="active-session-bar")
                with ScrollableContainer(id="todo-list"):
                    yield Static("", id="todo-list-content")

        yield Footer()

    # ── Mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._is_mounted = True
        self._check_morning_ritual()
        self._load_all()
        self._update_tag_selector()
        self._start_clock()
        self._check_active_session()

    # ── Daten laden ───────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._load_log()
        self._load_todos()
        self._load_carry_over()
        self._update_headers()

    def _load_log(self) -> None:
        self._log_entries = db.log_get_day(self.db_path, mode="work")
        self._render_log()

    def _load_todos(self) -> None:
        # Aktuelle Todo-ID merken um den Index nach Reload zu erhalten
        current_id = self._todos[self._todo_idx].id if self._todos else None
        self._todos = db.todo_list(self.db_path, mode="work")
        self._todos.sort(key=lambda t: (
            0 if t.status in ("active",)
            else 1 if t.status in ("open", "paused")
            else 2,
            t.created_at,
        ))
        # Index auf selbe Todo-ID zurücksetzen wenn noch vorhanden
        if current_id is not None:
            ids = [t.id for t in self._todos]
            self._todo_idx = ids.index(current_id) if current_id in ids else 0
        self._render_todos()

    def _load_carry_over(self) -> None:
        today = date.today().isoformat()
        self._carry_over = db.log_get_open_blocks(self.db_path, before_date=today)
        if self._carry_over:
            items = [e.content[:48] for e in self._carry_over[:3]]
            self._update("#carry-over-bar", Label, "  ↩  " + "  ·  ".join(items))
            self._add_class("#carry-over-bar", "visible")
        else:
            self._remove_class("#carry-over-bar", "visible")

    def _update_headers(self) -> None:
        now = datetime.now()
        day_meta = db.day_get(self.db_path)
        focus = day_meta.morning_focus if day_meta else None
        energy_str = ""
        if day_meta and day_meta.morning_energy:
            e = day_meta.morning_energy
            energy_str = " · " + "●" * e + "○" * (5 - e)

        focus_str = f" · {focus[:32]}" if focus else ""
        title_str = (
            f"  📋 LOG  ·  {now.strftime('%a, %d. %b')}  ·  "
            f"{len(self._log_entries)} Einträge{focus_str}{energy_str}"
        )
        self._update("#log-panel-title", Label, title_str)

        if focus:
            self._update("#morning-bar", Label, f"  Fokus: {focus}{energy_str}")
            self._add_class("#morning-bar", "visible")

        active_cnt  = sum(1 for t in self._todos if t.status in ("open", "active", "paused"))
        done_cnt    = sum(1 for t in self._todos if t.status == "done")
        self._update("#todo-panel-title", Label, 
            f"  ✅ TODOS  ·  {active_cnt} offen  ·  {done_cnt} done"
        )

    # ── Render ────────────────────────────────────────────────────────────────

    def _render_log(self) -> None:
        if not self._log_entries:
            content = "[dim]  (noch keine Einträge heute)[/]"
        else:
            lines = []
            for e in self._log_entries:
                tag = self.tags.get(e.tag_key)
                symbol = tag.symbol if tag else "·"
                color  = tag.color  if tag else "#888888"
                time_s = _fmt_time(e.created_at)
                tag_s  = f"{symbol} {e.tag_key:<7}"
                lines.append(
                    f"[dim]{time_s}[/]  [bold {color}]{tag_s}[/]  {escape(e.content)}"
                )
            content = "\n".join(lines)

        self._update("#log-list-content", Static, content)
        # Ans Ende scrollen
        w = self._q("#log-list", ScrollableContainer)
        if w is not None:
            try:
                w.scroll_end(animate=False)
            except Exception:
                pass

    def _render_todos(self) -> None:
        if not self._todos:
            content = "[dim]  (keine Todos – [a] um eines anzulegen)[/]"
            self._update("#todo-list-content", Static, content)
            return

        # Index in gültigem Bereich halten
        self._todo_idx = max(0, min(self._todo_idx, len(self._todos) - 1))

        lines = []
        for i, todo in enumerate(self._todos):
            selected = (i == self._todo_idx)
            icon    = STATUS_ICONS.get(todo.status, "○")
            p_color = PRIORITY_COLORS.get(todo.priority, "#C8C8C8")
            title_s = escape(todo.title[:38])
            ctx_s   = escape((todo.context or "")[:25])
            dur_s   = _fmt_duration(todo.total_duration_s) if todo.total_duration_s else ""
            sess_s  = f"{todo.total_sessions}×" if todo.total_sessions else ""
            stats   = f"{sess_s} {dur_s}".strip()

            dim = todo.status in ("done", "dropped")
            tc  = "#444466" if dim else p_color

            if selected:
                # Markierte Zeile: heller Hintergrund-Effekt via reverse
                arrow = "[bold #5B8DEF]▶[/]"
                line1 = f"{arrow} {icon}  [bold reverse {tc}] {title_s} [/]"
                line2 = f"     [dim]{ctx_s}[/]" + (f"  [dim]{stats}[/]" if stats else "") +                         "  [dim][↑↓] Nav  [f] Focus  [Enter] Aktiv  [d] Done  [x] Löschen[/]"
            else:
                line1 = f"  {icon}  [bold {tc}]{title_s}[/]"
                line2 = f"     [dim]{ctx_s}[/]" + (f"  [dim]{stats}[/]" if stats else "")

            lines.append(f"{line1}\n{line2}")
            lines.append("")

        self._update("#todo-list-content", Static, "\n".join(lines))

    # ── Morgen-Ritual ─────────────────────────────────────────────────────────

    def _check_morning_ritual(self) -> None:
        meta = db.day_get(self.db_path)
        if meta:
            return   # Ritual heute schon angeboten oder erledigt

        # DayMeta sofort anlegen: verhindert erneuten Dialog bei Modus-Wechseln
        # (z.B. Ctrl+A → WorkApp neu gestartet, aber Ritual schon gesehen)
        db.day_get_or_create(self.db_path)

        carry_texts = []
        today = date.today().isoformat()
        for e in db.log_get_open_blocks(self.db_path, before_date=today)[:4]:
            carry_texts.append(e.content[:55])

        def on_result(result: tuple[str, int] | None) -> None:
            if result:
                focus, energy = result
                db.day_set_morning(self.db_path, focus=focus, energy=energy)
            self._load_all()

        self.push_screen(MorningModal(carry_texts), on_result)

    # ── Uhr ───────────────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _start_clock(self) -> None:
        tick = 0
        while self._is_mounted:
            now = datetime.now()
            tick += 1

            # Session-Bar sekündlich aktualisieren
            if self._active_session:
                started = datetime.fromisoformat(self._active_session.started_at)
                elapsed = int((now - started).total_seconds())
                h = elapsed // 3600
                m = (elapsed % 3600) // 60
                s = elapsed % 60
                timer_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                self._update(
                    "#active-session-bar", Label,
                    f"  ▶  {self._active_session_title}  ·  {timer_str}"
                )
                self._add_class("#active-session-bar", "visible")
                sess_label = f"  ▶ {timer_str}"
            else:
                sess_label = ""

            # Titel + Modus nur jede Minute aktualisieren
            if tick % 60 == 1:
                mode = detect_mode(self.cfg.schedule, now)
                # In WorkApp nur Arbeit-relevante Labels – PRIVAT/WOCHENENDE
                # dürfen hier nicht erscheinen (Nutzer ist manuell in Work-Modus)
                mode_label = "FEIERABEND" if mode == Mode.HANDOVER else "ARBEIT"
                self.title = (
                    f"tui-log  ·  {mode_label}  ·  "
                    f"{now.strftime('%A, %d. %b')}  ·  "
                    f"{now.strftime('%H:%M')}"
                    f"{sess_label}"
                )

            await asyncio.sleep(1)

    # ── Aktive Session ────────────────────────────────────────────────────────

    def _check_active_session(self) -> None:
        sess = db.session_get_active(self.db_path)
        self._active_session = sess
        if sess:
            todo = db.todo_get(self.db_path, sess.todo_id)
            self._active_session_title = todo.title[:30] if todo else "?"
        else:
            self._active_session_title = ""
            self._remove_class("#active-session-bar", "visible")
        # Wenn Session aktiv: Bar wird vom Clock-Worker sekündlich befüllt

    # ── Log-Eingabe ───────────────────────────────────────────────────────────

    def action_focus_log_input(self) -> None:
        w = self._q("#log-text-input", LogInput)
        if w is not None:
            w.focus()

    def action_next_tag(self) -> None:
        if self._work_tags:
            self._tag_idx = (self._tag_idx + 1) % len(self._work_tags)
            self._update_tag_selector()

    def action_prev_tag(self) -> None:
        if self._work_tags:
            self._tag_idx = (self._tag_idx - 1) % len(self._work_tags)
            self._update_tag_selector()

    def _update_tag_selector(self) -> None:
        if not self._work_tags:
            return
        tag = self._work_tags[self._tag_idx]
        self._update("#tag-selector", Label, f"[bold {tag.color}] {tag.symbol} {tag.key} [/]")

    @on(Input.Submitted, "#log-text-input")
    def log_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or not self._work_tags:
            return
        tag_key = self._work_tags[self._tag_idx].key
        db.log_add(self.db_path, tag_key=tag_key, content=text, mode="work")
        event.input.clear()
        self._load_log()
        self._update_headers()

    # LogInput sendet TagNext/TagPrev statt Tab durchzulassen
    @on(LogInput.TagNext)
    def on_tag_next(self, _) -> None:
        self.action_next_tag()

    @on(LogInput.TagPrev)
    def on_tag_prev(self, _) -> None:
        self.action_prev_tag()

    # ── Todo-Navigation ──────────────────────────────────────────────────────

    def action_todo_up(self) -> None:
        if self._todos and self._todo_idx > 0:
            self._todo_idx -= 1
            self._render_todos()

    def action_todo_down(self) -> None:
        if self._todos and self._todo_idx < len(self._todos) - 1:
            self._todo_idx += 1
            self._render_todos()

    def action_todo_activate(self) -> None:
        """Enter: selektiertes Todo auf 'active' setzen ohne Session."""
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status in ("open", "paused"):
            db.todo_set_status(self.db_path, todo.id, "active")
            self._load_todos()
            self.notify(f"▶  {todo.title[:40]}", timeout=2)
        elif todo.status == "active":
            db.todo_set_status(self.db_path, todo.id, "paused")
            self._load_todos()
            self.notify(f"‖  {todo.title[:40]} pausiert", timeout=2)

    def action_todo_done(self) -> None:
        """d: selektiertes Todo als erledigt markieren."""
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status == "done":
            self.notify(f"Bereits erledigt: {todo.title[:40]}", timeout=2)
            return
        db.todo_set_status(self.db_path, todo.id, "done")
        # Optional: [done]-Eintrag ins Tages-Log
        db.log_add(self.db_path, tag_key="done", content=todo.title, mode="work")
        self._load_todos()
        self._load_log()
        self._update_headers()
        self.notify(f"✓  {todo.title[:40]}", timeout=2)

    def action_todo_delete(self) -> None:
        """x: selektiertes Todo löschen – mit Bestätigung."""
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]

        def on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            db.todo_delete(self.db_path, todo.id)
            self._todo_idx = max(0, self._todo_idx - 1)
            self._load_todos()
            self.notify(f"✗  '{todo.title[:40]}' gelöscht", timeout=2)

        self.push_screen(
            _ConfirmModal(f"'{todo.title[:50]}' wirklich löschen?"),
            on_confirm,
        )

    # ── Focus-Session starten ─────────────────────────────────────────────────

    def action_start_focus(self) -> None:
        try:
            self._do_start_focus()
        except Exception as e:
            import logging, traceback
            logging.error(f"action_start_focus:\n{traceback.format_exc()}")
            self.notify(f"Focus-Fehler: {e}", severity="error", timeout=4)

    def _do_start_focus(self) -> None:
        # Läuft bereits eine Session? Dann Modal dafür wieder öffnen.
        if self._active_session:
            existing_sess = db.session_get_active(self.db_path)
            if existing_sess:
                todo = db.todo_get(self.db_path, existing_sess.todo_id)
                if todo:
                    ctx_entries: list = []
                    self._open_focus_modal(todo, existing_sess, ctx_entries)
                    return
            # Session war in DB nicht mehr aktiv → State bereinigen
            self._active_session = None
            self._check_active_session()

        # Selektiertes Todo verwenden; Fallback auf erstes offenes
        if self._todos:
            todo = self._todos[self._todo_idx]
            if todo.status not in ("open", "paused", "active"):
                candidates = [t for t in self._todos if t.status in ("open", "paused", "active")]
                if not candidates:
                    self.notify("Keine offenen Todos.", severity="warning")
                    return
                todo = candidates[0]
        else:
            self.notify("Keine offenen Todos.", severity="warning")
            return

        # Kontext-Einträge (letzte Einträge mit ähnlichem Text)
        words = set(todo.title.lower().split())
        try:
            ctx_entries = [
                e for e in db.log_get_range(
                    self.db_path,
                    date_from=(date.today().replace(day=1).isoformat()),
                    date_to=date.today().isoformat(),
                )
                if any(w in e.content.lower() for w in words if len(w) > 3)
            ][-5:]
        except Exception:
            ctx_entries = []

        # Neue Session starten
        session = db.session_start(self.db_path, todo.id)
        self._active_session = session
        self._active_session_title = todo.title[:30]
        self._open_focus_modal(todo, session, ctx_entries)

    def _open_focus_modal(self, todo, session, ctx_entries: list) -> None:

        def on_focus_result(result: dict | None) -> None:
            if result is None:
                # Minimiert – Session läuft weiter
                return

            # Debriefing zeigen
            def on_debrief(debrief: dict | None) -> None:
                if debrief is None:
                    # Ohne Log-Eintrag beenden
                    db.session_end(
                        self.db_path, session.id,
                        outcome=result["outcome"],
                        log_entry="",
                    )
                else:
                    db.session_end(
                        self.db_path, session.id,
                        outcome=debrief["outcome"],
                        log_entry=debrief["log_entry"],
                    )
                    if debrief["log_entry"]:
                        tag_key = "done" if debrief["outcome"] == "solved" else "block"
                        db.log_add(
                            self.db_path,
                            tag_key=tag_key,
                            content=debrief["log_entry"],
                            mode="work",
                            todo_id=todo.id,
                        )

                    # Notizen aus der Session schreiben
                    for note_text in result.get("notes", []):
                        db.note_add(self.db_path, todo.id, note_text, session_id=session.id)

                self._active_session = None
                self._check_active_session()
                self._load_all()

            self.push_screen(
                DebriefingModal(
                    todo_title=todo.title,
                    elapsed_s=result["elapsed_s"],
                    suggested_outcome=result["outcome"],
                ),
                on_debrief,
            )

        self.push_screen(FocusModal(todo, ctx_entries), on_focus_result)

    # ── Todo anlegen ─────────────────────────────────────────────────────────

    def action_add_todo(self) -> None:
        """NewTodoModal öffnen – optionaler Prefill aus dem Log-Input."""
        prefill = (self._q("#log-text-input", LogInput) or type("", (), {"value": ""})()).value.strip()

        def on_result(result: dict | None) -> None:
            if not result:
                return
            db.todo_add(
                self.db_path,
                title=result["title"],
                context=result["context"],
                priority=result["priority"],
                mode=result["mode"],
            )
            # Log-Input leeren wenn er als Prefill diente
            if prefill:
                w = self._q("#log-text-input", LogInput)
                if w:
                    w.clear()
            self._load_todos()
            self._update_headers()
            self.notify(f"Todo angelegt: {result['title'][:40]}", timeout=2)

        self.push_screen(NewTodoModal(prefill_title=prefill), on_result)

    # ── Todos toggle ─────────────────────────────────────────────────────────

    def action_toggle_todos(self) -> None:
        panel = self._q("#todo-panel")
        if panel is None:
            return
        self._todos_visible = not self._todos_visible
        panel.display = self._todos_visible


    # ── Modus wechseln ───────────────────────────────────────────────────────

    def action_goto_work(self) -> None:
        self.exit("work")

    def action_goto_family(self) -> None:
        self.exit("family")

    def action_goto_weekend(self) -> None:
        self.exit("weekend")
    # ── Refresh ──────────────────────────────────────────────────────────────

    def action_refresh_all(self) -> None:
        self._load_all()
        self._check_active_session()
        self.notify("Aktualisiert.", timeout=1)


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_work_mode(config: AppConfig) -> None:
    app = WorkApp(config)
    app.run()
