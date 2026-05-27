"""
tui_log/work_app.py
~~~~~~~~~~~~~~~~~~~
Work-Modus TUI – Haupt-App.

Layout:
  ┌─ Header: Modus · Datum · Uhrzeit · Fokus ──────────────────┐
  │  LOG-PANEL (links 1/2)   │  TODO-PANEL (rechts 1/2)        │
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
import logging
import traceback
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Type, TypeVar, cast, overload

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Footer, Header, Input, Label, ListItem, ListView, Static
)
from textual import on, work

from rich.markup import escape

from .config import AppConfig
from . import db_utils as db
from .widgets.focus import FocusModal
from .widgets.debriefing import DebriefingModal
from .widgets.log_input import LogInput
from .widgets.new_todo import NewTodoModal
from .widgets.content_view import ContentEditModal, ContentView

# ── Tag-Hilfsfunktionen ───────────────────────────────────────────────────────

def _sym_w(s: str) -> int:
    """Visual terminal column width of a symbol (accounts for wide/emoji chars)."""
    w = 0
    for c in s:
        ew = unicodedata.east_asian_width(c)
        if ew in ('W', 'F'):
            w += 2
        elif unicodedata.category(c) not in ('Mn', 'Me', 'Cf'):
            w += 1
    return w

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
    except TypeError:
        return "??:??"

def _fmt_content(content: str) -> str:
    """Erste Zeile als Titel hervorheben, Rest als Body."""
    parts = content.split("\n", 1)
    title = f"[bold]{escape(parts[0])}[/bold]"
    if len(parts) > 1 and parts[1].strip():
        return title + "\n[dim]─────────────────────[/dim]\n" + escape(parts[1])
    return title

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
        sym_pad = " " * (2 - _sym_w(symbol))
        tag_s  = f"{symbol}{sym_pad} {entry.tag_key:<6}"
        first_line = entry.content.split("\n", 1)[0]
        has_body = "\n" in entry.content and entry.content.split("\n", 1)[1].strip()
        content_indicator_start = "[dim #FFEE2E]" if has_body else ""
        content_indicator_end = "[/] " if has_body else ""

        markup = (
            f"[dim]{time_s}[/]  "
            f"[bold {color}]{tag_s}[/]  "
            f"{content_indicator_start}{first_line}{content_indicator_end}"
        )
        super().__init__(markup, classes="log-entry")
        self.entry = entry

# ── Todo-Eintrag Widget ───────────────────────────────────────────────────────

STATUS_ICONS = {
    "open":    "[dim]○[/]",
    "active":  "[bold green]▶[/]",
    "paused":  "[dim]‖[/]",
    "done":    "[dim]✓[/]",
    "dropped":   "[dim]✗[/]",
    "cancelled": "[#8B0000]✗[/]",
    "focus":     "[bold #55CCFF]◉[/]",
}

STATUS_COLORS = {
    "done":      "#2E7D32",   # dunkelgrün
    "active":    "#66FF66",   # hellgrün
    "paused":    "#FFD700",   # gelb
    "cancelled": "#8B0000",   # dunkelrot
    "dropped": "#8B0000",   # dunkelrot
    "focus":   "#55CCFF",   # hellblau
    "open":    "#C8C8C8",   # neutral grau
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

        title_color = STATUS_COLORS.get(todo.status, "#C8C8C8")

        line1 = f"{icon} [bold {title_color}]{title_s}[/]"
        line2 = f"   [dim]{ctx_s}[/dim]" + (f"  [dim]{stats_s}[/]" if stats_s else "")

        markup = f"{line1}\n{line2}"
        super().__init__(markup, classes="todo-item")
        self.todo = todo

class TodoListContent(Static):
    """Subclass von Static, die Pfeiltasten im Todo-Panel abfängt.

    Leitet relevante Tasten an die App-Actions weiter und verhindert
    das Standard-Scrollen des Containers.
    """

    can_focus = True  # nötig damit .focus() greift und _on_key() Tasten empfängt

    async def _on_key(self, event) -> None:
        app = cast("WorkApp", self.app)
        k = event.key
        # Navigation
        if k in ("up", "j"):
            event.prevent_default()
            event.stop()
            app.action_todo_up()
        elif k in ("down", "k"):
            event.prevent_default()
            event.stop()
            app.action_todo_down()
        # Aktionen auf dem selektierten Todo
        elif k == "enter":
            event.prevent_default()
            event.stop()
            app.action_todo_activate()
        elif k == "f":
            event.prevent_default()
            event.stop()
            await app.action_start_focus()
        elif k == "d":
            event.prevent_default()
            event.stop()
            app.action_todo_done()
        elif k == "x":
            event.prevent_default()
            event.stop()
            app.action_todo_delete()
        else:
            try:
                await super()._on_key(event)
            except Exception:
                pass


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

# ── Tag-Auswahl-Modal ─────────────────────────────────────────────────────────

class TagSelectModal(ModalScreen):
    """Tag-Picker für Log-Einträge. Gibt den gewählten tag_key zurück oder None."""

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
    ]

    DEFAULT_CSS = """
    TagSelectModal { align: center middle; }
    #tag-select-dialog {
        background: #0E1117;
        border: solid #334;
        width: 38;
        height: auto;
        padding: 1 2;
    }
    #tag-select-title { color: #666688; margin-bottom: 1; }
    #tag-select-hint  { color: #444466; margin-top: 1; }
    """

    def __init__(self, tags, current_key: str) -> None:
        super().__init__()
        self._tag_list = list(tags)
        self._current  = current_key

    def compose(self) -> ComposeResult:
        with Vertical(id="tag-select-dialog"):
            yield Label("Tag wählen", id="tag-select-title")
            yield ListView(id="tag-list")
            yield Label("↑↓ Navigieren  Enter Übernehmen  Esc Abbrechen", id="tag-select-hint")

    def on_mount(self) -> None:
        lv = self.query_one("#tag-list", ListView)
        current_idx = 0
        for i, tag in enumerate(self._tag_list):
            sym_pad = " " * (2 - _sym_w(tag.symbol))
            row = f"[bold {tag.color}]{tag.symbol}{sym_pad} {tag.key:<8}[/]  [dim]{tag.name}[/]"
            lv.append(ListItem(Static(row)))
            if tag.key == self._current:
                current_idx = i
        lv.index = current_idx
        lv.focus()

    @on(ListView.Selected, "#tag-list")
    def _selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._tag_list):
            self.dismiss(self._tag_list[idx].key)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

# ── Haupt-App ─────────────────────────────────────────────────────────────────

class WorkApp(App):

    CSS_PATH = "work.tcss"

    BINDINGS = [
        Binding("a",         "add_todo",        "Neu Todo",     show=True),
        Binding("b",         "prev_filter",     "Filter ←",     show=False),
        Binding("d",         "todo_done",       "✓ Done",       show=False),
        Binding("down,k",    "todo_down",       "Todo ↓",       show=False),
        Binding("c",         "change_tag",      "Tag",         show=False),
        Binding("e",         "edit_entry",      "Edit Entry",  show=False),
        Binding("enter",     "todo_activate",   "Aktivieren",   show=False),
        Binding("f",         "start_focus",     "Focus",        show=True),
        Binding("m",         "toggle_content",  "Content",      show=True),
        Binding("n",         "next_filter",     "Filter →",     show=False),
        Binding("q",         "quit",            "Beenden",      show=True),
        Binding("r",         "refresh_all",     "Refresh",      show=False),
        Binding("shift+d",   "delete_entry",    "Del Entry",    show=False),
        Binding("shift+p",   "git_push_db",     "Push DB",      show=True),
        Binding("shift+tab", "prev_tag",        "Tag",          show=False),
        Binding("space,n",   "focus_log_input", "Log",          show=True),
        Binding("t",         "toggle_todos",    "Todos",        show=True),
        Binding("tab",       "next_tag",        "Tag",          show=False),
        Binding("up,j",      "todo_up",         "Todo ↑",       show=False),
        Binding("v",         "view_latest",     "View Entry",  show=False),
        Binding("x",         "todo_delete",     "✗ Cancel",     show=False),
    ]

    # Reaktiver State
    _tag_idx:        reactive[int]  = reactive(0)
    _todos_visible:  reactive[bool] = reactive(True)
    _content_visible: reactive[bool] = reactive(True)
    _active_session: reactive[db.FocusSession | None] = reactive(None)
    _clock_str:      reactive[str]  = reactive("")
    _log_filter:     reactive[str | None] = reactive(None)  # None = alle Tags

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
        self._active_session_base_s: int = 0  # kumulierte Dauer des Todo vor aktueller Session
        self._focus_starting: bool = False    # Reentry-Guard gegen doppeltes F
        self._filter_keys: list[str | None] = []  # [None, "done", "start", ...] – wird in on_mount befüllt
        self._displayed_entry_id: int | None = None

    # ── Sichere UI-Helfer ─────────────────────────────────────────────────────

    _W = TypeVar("_W", bound=Widget)

    @overload
    def _q(self, selector: str, widget_type: Type[_W]) -> _W | None: ...
    @overload
    def _q(self, selector: str) -> Widget | None: ...
    def _q(self, selector: str, widget_type=None):
        """query_one das nie wirft – gibt None zurück wenn Widget nicht gefunden."""
        try:
            if widget_type:
                return self.query_one(selector, widget_type)
            return self.query_one(selector)
        except NoMatches:
            return None

    def _update(self, selector: str, widget_type: Type[Static], content: str) -> None:
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
                yield Label("", id="log-filter-bar")
                yield Label("", id="carry-over-bar")

                with ScrollableContainer(id="log-list"):
                    yield ListView(id="log-list-view")

                with Horizontal(id="log-input-row"):
                    yield Label("", id="tag-selector")
                    yield LogInput(
                        placeholder="Eintrag… (Tab = Tag wechseln)",
                        id="log-text-input",
                    )

            # ── Content-Panel (mittig, fixe Breite) ─────────────────
            with Vertical(id="content-panel"):
                yield Label("", id="content-panel-title")
                with ScrollableContainer(id="content-panel-body"):
                    yield ContentView("", id="log-entry-content")

            # ── Todo-Panel ────────────────────────────────────
            with Vertical(id="todo-panel"):
                yield Label("", id="todo-panel-title")
                yield Label("", id="active-session-bar")
                with ScrollableContainer(id="todo-list"):
                        yield TodoListContent("", id="todo-list-content")

        yield Footer()

    # ── Mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._is_mounted = True
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
        self._log_entries = db.log_get_all(self.db_path, mode="work")
        # Filter-Leiste: nur Tags mit Einträgen anzeigen
        used = db.log_used_tags(self.db_path, mode="work")
        self._filter_keys = [None] + [t.key for t in self._work_tags if t.key in used]
        if self._log_filter not in self._filter_keys:
            self._log_filter = None
        self._render_filter_bar()
        self._render_log()

    def _load_todos(self) -> None:
        # Aktuelle Todo-ID merken um den Index nach Reload zu erhalten
        current_id = self._todos[self._todo_idx].id if self._todos else None
        self._todos = db.todo_list(self.db_path, mode="work")
        self._todos.sort(key=lambda t: (
            0 if t.status in ("active",)
            else 1 if t.status in ("open", "paused")
            else 2 if t.status == "done"
            else 3,
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

        today = date.today().isoformat()
        today_count = sum(1 for e in self._log_entries if e.date == today)
        focus_str = f" · {focus[:32]}" if focus else ""
        title_str = (
            f"  📋 LOG  ·  {now.strftime('%a, %d. %b')}  ·  "
            f"{today_count} Einträge heute{focus_str}{energy_str}"
        )
        self._update("#log-panel-title", Label, title_str)

        active_cnt  = sum(1 for t in self._todos if t.status in ("open", "active", "paused"))
        done_cnt    = sum(1 for t in self._todos if t.status == "done")
        self._update("#todo-panel-title", Label, 
            f"  ✅ TODOS  ·  {active_cnt} offen  ·  {done_cnt} done"
        )

    # ── Render ────────────────────────────────────────────────────────────────

    def _render_log(self) -> None:
        entries = self._log_entries
        if self._log_filter is not None:
            entries = [e for e in entries if e.tag_key == self._log_filter]
        lv = self._q("#log-list-view", ListView)
        if lv is not None:
            lv.clear()
            if not entries:
                if self._log_filter is not None:
                    tag = self.tags.get(self._log_filter)
                    label = f"{tag.symbol} {tag.key}" if tag else self._log_filter
                    lv.append(ListItem(Static(f"[dim]  (keine Einträge für {label})[/]")))
                else:
                    lv.append(ListItem(Static("[dim]  (noch keine Einträge)[/]") ))
            else:
                today = date.today().isoformat()
                current_date = None
                for e in entries:
                    if e.date != current_date:
                        current_date = e.date
                        if e.date == today:
                            date_label = "Heute"
                        else:
                            try:
                                d = date.fromisoformat(e.date)
                                date_label = d.strftime("%a, %d. %b %Y")
                            except ValueError:
                                date_label = e.date
                        lv.append(ListItem(Static(f"[dim]── {date_label} ──────────────────────[/]")))
                    lv.append(ListItem(LogEntryWidget(e, self.tags)))

        # Zeige Detail-Content des neuesten Eintrags (falls vorhanden)
        if entries:
            self._displayed_entry_id = entries[0].id
            self._update("#log-entry-content", ContentView, _fmt_content(entries[0].content))
        else:
            self._displayed_entry_id = None
            self._update("#log-entry-content", ContentView, "[dim]  (kein Inhalt)[/]")

        # Nach oben scrollen – neueste Einträge zuerst
        w = self._q("#log-list", ScrollableContainer)
        if w is not None:
            try:
                w.scroll_home(animate=False)
            except Exception:
                pass

    def _render_todos(self) -> None:
        if not self._todos:
            content = "[dim]  (keine Todos – [a] um eines anzulegen)[/]"
            self._update("#todo-list-content", Static, content)
            return

        # Index in gültigem Bereich halten
        self._todo_idx = max(0, min(self._todo_idx, len(self._todos) - 1))

        # Todo mit aktiver Focus-Session ermitteln
        focus_todo_id = self._active_session.todo_id if self._active_session else None

        lines = []
        for i, todo in enumerate(self._todos):
            selected = (i == self._todo_idx)
            is_focus = (todo.id == focus_todo_id)
            effective_status = "focus" if is_focus else todo.status
            icon    = STATUS_ICONS.get(effective_status, "○")
            tc      = STATUS_COLORS.get(effective_status, "#C8C8C8")
            ctx_s   = escape((todo.context or "")[:25])
            dur_s   = _fmt_duration(todo.total_duration_s) if todo.total_duration_s else ""
            sess_s  = f"{todo.total_sessions}×" if todo.total_sessions else ""
            stats   = f"{sess_s} {dur_s}".strip()

            if selected:
                # Markierte Zeile: heller Hintergrund-Effekt via reverse
                arrow = "[bold #5B8DEF]▶[/]"
                line1 = f"{arrow} {icon}  [bold reverse {tc}] {todo.title}[/]"
                line2 = f"     [dim]{ctx_s}[/]" + (f"  [dim]{stats}[/]" if stats else "") +                         "  [dim][f] Focus  [Enter] Aktiv  [d] Done  [x] Cancel[/]"
            else:
                line1 = f"  {icon}  [bold {tc}]{todo.title}[/]"
                line2 = f"     [dim]{ctx_s}[/]" + (f"  [dim]{stats}[/]" if stats else "")

            lines.append(f"{line1}\n{line2}")
            lines.append("")

        self._update("#todo-list-content", Static, "\n".join(lines))

    # ── Uhr ───────────────────────────────────────────────────────────────────

    @work(exclusive=True, exit_on_error=False)
    async def _start_clock(self) -> None:
        tick = 0
        while self._is_mounted:
            now = datetime.now()
            tick += 1

            # Session-Bar sekündlich aktualisieren – KEIN DB-Call hier!
            if self._active_session:
                started = datetime.fromisoformat(self._active_session.started_at)
                elapsed = self._active_session_base_s + int((now - started).total_seconds())
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

            self.title = ('my daily journal')

            await asyncio.sleep(1)

    # ── Aktive Session ────────────────────────────────────────────────────────

    def _check_active_session(self) -> None:
        sess = db.session_get_active(self.db_path)
        self._active_session = sess
        if sess:
            todo = db.todo_get(self.db_path, sess.todo_id)
            self._active_session_title = todo.title[:30] if todo else "?"
            self._active_session_base_s = int(todo.total_duration_s) if todo else 0
        else:
            self._active_session_title = ""
            self._active_session_base_s = 0
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

    # ── Log-Filter ────────────────────────────────────────────────────────────

    def action_next_filter(self) -> None:
        if not self._filter_keys:
            return
        idx = self._filter_keys.index(self._log_filter) if self._log_filter in self._filter_keys else 0
        self._log_filter = self._filter_keys[(idx + 1) % len(self._filter_keys)]
        self._render_filter_bar()
        self._render_log()

    def action_view_latest(self) -> None:
        """Tastenkürzel: zeigt den Inhalt des neuesten Log-Eintrags an."""
        if self._log_entries:
            self._update("#log-entry-content", ContentView, _fmt_content(self._log_entries[0].content))
        else:
            self._update("#log-entry-content", ContentView, "[dim]  (kein Inhalt)[/]")

    def action_edit_entry(self) -> None:
        """Öffnet einen Editor für den aktuell angezeigten Log-Eintrag."""
        if not self._displayed_entry_id:
            self.notify("Kein Eintrag ausgewählt", timeout=2)
            return

        entry = db.log_get(self.db_path, self._displayed_entry_id)
        if not entry:
            self.notify("Eintrag nicht gefunden", severity="error", timeout=2)
            return

        def _on_result(result: str | None) -> None:
            if result is None:
                return
            try:
                db.log_update(self.db_path, entry.id, content=result)
                self._load_log()
                self._update_headers()
                self.notify("Eintrag gespeichert", timeout=2)
            except Exception as e:
                logging.error(f"edit_entry save failed:\n{traceback.format_exc()}")
                self.notify(f"Fehler beim Speichern: {e}", severity="error", timeout=4)

        self.push_screen(ContentEditModal(entry.content), _on_result)

    def action_change_tag(self) -> None:
        """Tag des aktuell angezeigten Log-Eintrags ändern."""
        if not self._displayed_entry_id:
            self.notify("Kein Eintrag ausgewählt", timeout=2)
            return
        entry = db.log_get(self.db_path, self._displayed_entry_id)
        if not entry:
            self.notify("Eintrag nicht gefunden", severity="error", timeout=2)
            return

        def _on_result(new_key: str | None) -> None:
            if new_key is None or new_key == entry.tag_key:
                return
            try:
                db.log_update(self.db_path, entry.id, tag_key=new_key)
                self._load_log()
                self._update_headers()
                self.notify(f"Tag → {new_key}", timeout=2)
            except Exception as e:
                logging.error(f"change_tag failed:\n{traceback.format_exc()}")
                self.notify(f"Fehler: {e}", severity="error", timeout=4)

        self.push_screen(TagSelectModal(self.tags, entry.tag_key), _on_result)

    def action_delete_entry(self) -> None:
        """Shift+D: aktuell angezeigten Log-Eintrag löschen – mit Bestätigung."""
        if not self._displayed_entry_id:
            self.notify("Kein Eintrag ausgewählt", timeout=2)
            return
        entry = db.log_get(self.db_path, self._displayed_entry_id)
        if not entry:
            self.notify("Eintrag nicht gefunden", severity="error", timeout=2)
            return

        preview = entry.content.split("\n", 1)[0][:50]

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            db.log_delete(self.db_path, entry.id)
            self._displayed_entry_id = None
            self._load_log()
            self._update_headers()
            self.notify("Eintrag gelöscht", timeout=2)

        self.push_screen(_ConfirmModal(f"Eintrag löschen: '{preview}'?"), _on_confirm)

    @on(ListView.Highlighted)
    def on_list_view_highlighted(self, message: ListView.Highlighted) -> None:
        """When the highlighted item changes (arrow keys), update the middle content panel."""
        item = getattr(message, "item", None)
        if item is None:
            return
        try:
            lew = item.query_one(LogEntryWidget)
        except NoMatches:
            return
        entry = getattr(lew, "entry", None)
        if not entry:
            return
        self._displayed_entry_id = entry.id
        self._update("#log-entry-content", ContentView, _fmt_content(entry.content))

    @on(ListView.Selected)
    def on_list_view_selected(self, message: ListView.Selected) -> None:
        """When an item is selected (Enter), also update content and focus content panel."""
        item = getattr(message, "item", None)
        if item is None:
            return
        try:
            lew = item.query_one(LogEntryWidget)
        except NoMatches:
            return
        entry = getattr(lew, "entry", None)
        if not entry:
            return
        self._displayed_entry_id = entry.id
        self._update("#log-entry-content", ContentView, _fmt_content(entry.content))

    def action_prev_filter(self) -> None:
        if not self._filter_keys:
            return
        idx = self._filter_keys.index(self._log_filter) if self._log_filter in self._filter_keys else 0
        self._log_filter = self._filter_keys[(idx - 1) % len(self._filter_keys)]
        self._render_filter_bar()
        self._render_log()

    def _render_filter_bar(self) -> None:
        """Filter-Leiste: zeigt alle Tags als Chips, aktiver hervorgehoben."""
        if not self._filter_keys:
            return
        parts = []
        for key in self._filter_keys:
            if key is None:
                label = "Alle"
                if self._log_filter is None:
                    parts.append("[bold reverse #5B8DEF] Alle [/]")
                else:
                    parts.append("[dim]Alle[/]")
            else:
                tag = self.tags.get(key)
                sym = tag.symbol if tag else "·"
                color = tag.color if tag else "#888888"
                if self._log_filter == key:
                    parts.append(f"[bold reverse {color}] {sym} {key} [/]")
                else:
                    parts.append(f"[dim]{sym} {key}[/]")
        self._update("#log-filter-bar", Label, "  " + "  ".join(parts) + "   [dim]\\[  ] Filter[/]")

    @on(ListView.Selected, "#log-list-view")
    def _on_log_selected(self, event) -> None:
        """When a log list item is selected, show its full content in the detail pane."""
        try:
            li = event.item
            widget = li.query_one(LogEntryWidget)
            entry = widget.entry
            self._displayed_entry_id = entry.id
            self._update("#log-entry-content", ContentView, _fmt_content(entry.content))
        except (NoMatches, AttributeError):
            pass

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
        # Aktive Focus-Session für dieses Todo beenden
        if self._active_session and self._active_session.todo_id == todo.id:
            db.session_end(self.db_path, self._active_session.id, outcome="solved", log_entry="")
            self._active_session = None
            self._active_session_title = ""
            self._active_session_base_s = 0
            self._check_active_session()
        db.todo_set_status(self.db_path, todo.id, "done")
        # Optional: [done]-Eintrag ins Tages-Log
        db.log_add(self.db_path, tag_key="done", content=todo.title, mode="work")
        self._load_todos()
        self._load_log()
        self._update_headers()
        self.notify(f"✓  {todo.title[:40]}", timeout=2)

    def action_todo_delete(self) -> None:
        """x: selektiertes Todo canceln – mit Bestätigung."""
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status == "cancelled":
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            # Aktive Focus-Session für dieses Todo beenden
            if self._active_session and self._active_session.todo_id == todo.id:
                db.session_end(self.db_path, self._active_session.id, outcome="open", log_entry="")
                self._active_session = None
                self._active_session_title = ""
                self._active_session_base_s = 0
                self._check_active_session()
            db.todo_set_status(self.db_path, todo.id, "cancelled")
            self._load_todos()
            self.notify(f"✗  '{todo.title[:40]}' cancelled", timeout=2)

        self.push_screen(
            _ConfirmModal(f"'{todo.title[:50]}' wirklich canceln?"),
            on_confirm,
        )

    # ── Focus-Session starten ─────────────────────────────────────────────────

    def action_start_focus(self) -> None:
        logging.debug("action_start_focus: ENTER")
        if self._focus_starting:
            logging.error("action_start_focus: reentry blocked (focus-modal already opening)")
            return
        self._focus_starting = True
        try:
            self._do_start_focus()
            logging.debug("action_start_focus: _do_start_focus returned")
        except Exception as e:
            logging.error(f"action_start_focus:\n{traceback.format_exc()}")
            self.notify(f"Focus-Fehler: {e}", severity="error", timeout=4)
        finally:
            self._focus_starting = False

    def _do_start_focus(self) -> None:
        logging.debug(f"_do_start_focus: todos={len(self._todos) if self._todos else 0} idx={self._todo_idx}")
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

        # Aktive Session ggf. auf anderes Todo umschalten
        existing_sess = db.session_get_active(self.db_path)
        if existing_sess:
            if existing_sess.todo_id == todo.id:
                # Toggle aus: gleiche Todo-Auswahl + [f] beendet aktive Session
                # und persistiert die Laufzeit.
                db.session_end(self.db_path, existing_sess.id, outcome="open", log_entry="")
                self._active_session = None
                self._active_session_title = ""
                self._active_session_base_s = 0
                self._check_active_session()
                self._load_todos()
                self._update_headers()
                self.notify(f"Focus beendet: {todo.title[:40]}", timeout=2)
                return

            # Bisherige Session sauber als "open" beenden und auf neues Todo wechseln.
            db.session_end(self.db_path, existing_sess.id, outcome="open", log_entry="")

        # Neue Session starten
        logging.debug(f"_do_start_focus: starting session for todo id={todo.id} title={todo.title[:30]!r}")
        session = db.session_start(self.db_path, todo.id)
        logging.debug(f"_do_start_focus: session_start returned id={session.id}")
        self._active_session = session
        self._active_session_title = todo.title[:30]
        stats_todo = db.todo_get(self.db_path, todo.id)
        self._active_session_base_s = int(stats_todo.total_duration_s) if stats_todo else 0
        ctx_entries = db.log_get_day(self.db_path)
        logging.debug(f"_do_start_focus: ctx_entries={len(ctx_entries)}")
        self._open_focus_modal(todo, session, ctx_entries)
        logging.debug("_do_start_focus: _open_focus_modal returned")

    def _open_focus_modal(self, todo, session, ctx_entries: list) -> None:

        def on_focus_result(result: dict | None) -> None:
            if result is None:
                # Minimiert – Session läuft weiter
                return

            # Debriefing zeigen
            def on_debrief(debrief: dict | None) -> None:
                try:
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
                    self._active_session_title = ""
                    self._check_active_session()
                    self._load_all()
                except Exception as e:
                    logging.error(f"on_debrief:\n{traceback.format_exc()}")
                    self.notify(f"Fehler beim Speichern: {e}", severity="error", timeout=5)
                    self._active_session = None
                    self._active_session_title = ""
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

        logging.debug(f"_open_focus_modal: creating FocusModal (ctx={len(ctx_entries)})")

        # DEBUG: Minimal-Modal zum Einkreisen des Mount-Problems
        import os
        if os.environ.get("TUILOG_TEST_MODAL"):
            from .widgets.focus import _TestModal
            self.push_screen(_TestModal(), lambda r: logging.debug(f"_TestModal dismissed: {r}"))
            return
        if os.environ.get("TUILOG_MINIMAL_MODAL"):
            from textual.screen import ModalScreen as _MS
            from textual.widgets import Label as _L
            class _MinModal(_MS):
                DEFAULT_CSS = "_MinModal { align: center middle; } #m { background: #222; border: solid red; padding: 2; width: 40; height: 5; }"
                def compose(self):
                    logging.debug("_MinModal.compose: ENTER")
                    yield _L("HELLO MINIMAL MODAL", id="m")
                def on_mount(self):
                    logging.debug("_MinModal.on_mount: ENTER")
            self.push_screen(_MinModal(), lambda r: logging.debug(f"_MinModal dismissed: {r}"))
            return

        try:
            modal = FocusModal(todo, ctx_entries)
        except Exception as e:
            logging.error(f"FocusModal __init__ failed:\n{traceback.format_exc()}")
            self.notify(f"Focus-Modal-Fehler: {e}", severity="error", timeout=5)
            return
        logging.debug("_open_focus_modal: pushing screen")
        try:
            self.push_screen(modal, on_focus_result)
            logging.debug("_open_focus_modal: push_screen returned")
        except Exception as e:
            logging.error(f"push_screen(FocusModal) failed:\n{traceback.format_exc()}")
            self.notify(f"Focus-Modal-Fehler: {e}", severity="error", timeout=5)
            return

        def _post_push_check() -> None:
            try:
                scr = self.screen
                stack = [type(s).__name__ for s in self.screen_stack]
                logging.debug(f"_post_push_check: active_screen={type(scr).__name__} stack={stack} modal_mounted={modal.is_mounted}")
                if not modal.is_mounted:
                    # Hard fail-safe: If FocusModal didn't mount, remove it from stack
                    # so the app never gets stuck on an unresponsive screen.
                    logging.error("_post_push_check: FocusModal failed to mount; recovering by popping screen")
                    try:
                        self.pop_screen()
                    except Exception:
                        logging.error(f"_post_push_check(pop_screen):\n{traceback.format_exc()}")
                    self.notify(
                        "Focus-Dialog konnte nicht angezeigt werden. Session läuft im Hintergrund weiter.",
                        severity="warning",
                        timeout=5,
                    )
            except Exception:
                logging.error(f"_post_push_check:\n{traceback.format_exc()}")

        self.set_timer(0.2, _post_push_check)
        self.set_timer(1.5, _post_push_check)

    # ── Todo anlegen ─────────────────────────────────────────────────────────

    def action_add_todo(self) -> None:
        """NewTodoModal öffnen – optionaler Prefill aus dem Log-Input."""
        _inp = self._q("#log-text-input", LogInput)
        prefill = _inp.value.strip() if _inp is not None else ""

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
        # Wenn das Todo-Panel sichtbar wird, fokusieren wir die Todo-Liste
        # damit Pfeiltasten dort statt am Container verarbeitet werden.
        if self._todos_visible:
            w = self._q("#todo-list-content", TodoListContent)
            if w is not None:
                try:
                    w.focus()
                except Exception:
                    pass

    def action_toggle_content(self) -> None:
        panel = self._q("#content-panel")
        if panel is None:
            return
        self._content_visible = not self._content_visible
        panel.display = self._content_visible

    # ── Refresh ──────────────────────────────────────────────────────────────

    def action_refresh_all(self) -> None:
        self._load_all()
        self._check_active_session()
        self.notify("Aktualisiert.", timeout=1)

    def action_git_push_db(self) -> None:
        self._run_git_push()

    @work
    async def _run_git_push(self) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cwd = str(self.db_path.parent)
        db_name = self.db_path.name

        async def run(*args: str) -> tuple[int, str]:
            proc = await asyncio.create_subprocess_exec(
                *args, cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            return proc.returncode or 0, (out + err).decode(errors="replace")

        rc, _ = await run("git", "add", db_name)
        if rc != 0:
            self.notify("git add fehlgeschlagen", severity="error", timeout=4)
            return

        rc, out = await run("git", "commit", "-m", f"update {timestamp}")
        if rc != 0:
            if "nothing to commit" in out:
                self.notify("Keine Änderungen – nichts zu pushen", timeout=3)
            else:
                self.notify("git commit fehlgeschlagen", severity="error", timeout=4)
            return

        rc, _ = await run("git", "push")
        if rc == 0:
            self.notify(f"journal.db gepushed  [{timestamp}]", timeout=3)
        else:
            self.notify("git push fehlgeschlagen", severity="error", timeout=4)

# ── Entry Point ───────────────────────────────────────────────────────────────

def run_work_mode(config: AppConfig) -> None:
    app = WorkApp(config)
    app.run()
