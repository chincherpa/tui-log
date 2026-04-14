"""
tui_log/modes/weekend.py
~~~~~~~~~~~~~~~~~~~~~~~~
Wochenend-Modus – Sa/So.

Layout:
  ┌─ Header: WOCHENENDE · Datum ────────────────────────────────┐
  │  PROJEKT-PANEL (1fr) │  LOG-PANEL (2fr)  │  TODO-PANEL (1fr) │
  │  Aktive Projekte     │  Log des Tages    │  Wochenend-Todos  │
  │  [Phase-Badges]      │  [Tag] Eingabe    │                   │
  ├─ Footer: Keybindings ──────────────────────────────────────┤

Tags: bau, gart, foto, pause, note
"""

from __future__ import annotations

import asyncio
import unicodedata
from datetime import date, datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, Static
from textual import on, work

from rich.markup import escape

from ..config import AppConfig
from .. import db_utils as db
from ..widgets.log_input import LogInput

# ── Helfer ────────────────────────────────────────────────────────────────────

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


def _fmt_time(iso_dt: str) -> str:
    try:
        return iso_dt[11:16]
    except Exception:
        return "??:??"

PHASE_BADGES = {
    "planning": ("📐", "#666688"),
    "active":   ("▶",  "#00C896"),
    "paused":   ("‖",  "#FFD93D"),
    "done":     ("✓",  "#444466"),
}

_STATUS_ICONS = {
    "open":    "[dim]○[/]",
    "active":  "[bold green]▶[/]",
    "paused":  "[dim]‖[/]",
    "done":    "[dim]✓[/]",
    "dropped": "[dim]✗[/]",
}

# ── Neues Projekt Modal ───────────────────────────────────────────────────────

class NewProjectModal(ModalScreen[dict | None]):
    """Anlegen eines neuen Projekts."""

    BINDINGS = [Binding("escape", "cancel", "Abbrechen")]

    def __init__(self, weekend_tags: list) -> None:
        super().__init__()
        self._weekend_tags = weekend_tags
        self._tag_idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="project-dialog"):
            yield Label("🔨  Neues Projekt", id="project-title")
            yield Label("Name:", classes="project-label")
            yield LogInput(placeholder="z.B. Gartenhaus, Hochbeet…", id="project-name-input", classes="project-input")
            yield Label("Tag:", classes="project-label")
            yield Label(self._tag_str(), id="project-tag-display")
            yield Label("[Tab] Tag  [Enter] Anlegen  [Esc] Abbrechen", id="project-hint")

    DEFAULT_CSS = """
    NewProjectModal { align: center middle; }
    #project-dialog {
        background: #0D1A0D;
        border: solid #7BC67E;
        width: 52;
        height: auto;
        padding: 1 2;
    }
    #project-title  { color: #7BC67E; text-style: bold; height: 1; margin-bottom: 1; }
    .project-label  { color: #C8C8C8; text-style: bold; height: 1; }
    .project-input  { background: #1A2A1A; color: #E8E8E8; border: solid #2A3A2A; margin-bottom: 1; }
    .project-input:focus { border: solid #7BC67E; }
    #project-tag-display { color: #7BC67E; text-style: bold; height: 1; margin-bottom: 1; }
    #project-hint   { color: #555577; height: 1; }
    """

    def _tag_str(self) -> str:
        if not self._weekend_tags:
            return "(keine Tags)"
        parts = []
        for i, t in enumerate(self._weekend_tags):
            label = f"{t.symbol} {t.key}"
            parts.append(f"[{label}]" if i == self._tag_idx else label)
        return "  " + "   ".join(parts)

    def _update_tag(self) -> None:
        self._update("#project-tag-display", Label, self._tag_str())

    def on_key(self, event) -> None:
        if event.key == "tab" and self._weekend_tags:
            self._tag_idx = (self._tag_idx + 1) % len(self._weekend_tags)
            self._update_tag()
            event.stop()

    @on(Input.Submitted, "#project-name-input")
    def submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if not name:
            return
        tag_key = self._weekend_tags[self._tag_idx].key if self._weekend_tags else None
        self.dismiss({"name": name, "tag_key": tag_key})

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        (lambda w: w.focus() if w else None)(self._q("#project-name-input", Input))

# ── Haupt-App ─────────────────────────────────────────────────────────────────

class WeekendApp(App):

    BINDINGS = [
        Binding("space,n",   "focus_input",    "Log",           show=True),
        Binding("tab",       "next_tag",       "Tag",           show=False),
        Binding("shift+tab", "prev_tag",       "Tag",           show=False),
        Binding("p",         "new_project",    "Neu Projekt",   show=True),
        Binding("shift+down","next_project",   "Projekt ▼",    show=False),
        Binding("shift+up",  "prev_project",   "Projekt ▲",    show=False),
        Binding("a",         "add_todo",       "Neu Todo",      show=True),
        Binding("up,k",      "todo_up",        "Todo ↑",        show=False),
        Binding("down,j",    "todo_down",      "Todo ↓",        show=False),
        Binding("d",         "todo_done",      "✓ Todo",        show=False),
        Binding("shift+d",   "done_project",   "✓ Projekt",     show=True),
        Binding("x",         "todo_delete",    "✗ Löschen",     show=False),
        Binding("w",         "show_week",      "Woche",         show=True),
        Binding("r",         "refresh",        "Refresh",       show=False),
        Binding("ctrl+a",    "goto_work",      "→ Arbeit",      show=True),
        Binding("ctrl+f",    "goto_family",    "→ Familie",     show=True),
        Binding("ctrl+w",    "goto_weekend",   "→ Wochenende",  show=True),
        Binding("q",         "quit",           "Beenden",       show=True),
        Binding("shift+p",   "git_push_db",    "Push DB",       show=True),
    ]

    DEFAULT_CSS = """
    Screen  { background: #0D0D1A; color: #C8C8C8; }
    Header  { background: #12100A; color: #C8A165; height: 1; }
    Footer  { background: #12100A; color: #555577; height: 1; }

    #main-split { layout: horizontal; height: 1fr; }

    /* ── Projekt-Panel ── */
    #project-panel {
        width: 1fr;
        border: solid #2A2A18;
        padding: 0 1;
    }
    #project-panel:focus-within { border: solid #C8A165; }
    #project-title-bar {
        background: #12100A;
        color: #C8A165;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    #project-list { height: 1fr; overflow-y: auto; }

    /* ── Log-Panel ── */
    #log-panel {
        width: 2fr;
        border: solid #2A2A18;
        padding: 0 1;
    }
    #log-panel:focus-within { border: solid #C8A165; }
    #log-title-bar {
        background: #12100A;
        color: #C8A165;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    #log-list      { height: 1fr; overflow-y: auto; }
    #input-row     { height: 3; layout: horizontal; background: #12100A; border-top: solid #2A2A18; padding: 0 1; align: left middle; }
    #tag-selector  { width: auto; min-width: 12; height: 1; background: #1A1A0A; color: #C8A165; text-style: bold; padding: 0 1; margin-right: 1; }
    #log-input     { width: 1fr; height: 1; background: #12100A; color: #E8E8E8; border: none; }
    #log-input:focus { border: none; background: #12100A; }

    /* ── Todo-Panel ── */
    #todo-panel {
        width: 1fr;
        border: solid #2A2A18;
        padding: 0 1;
    }
    #todo-panel:focus-within { border: solid #C8A165; }
    #todo-panel-title {
        background: #12100A;
        color: #C8A165;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    #todo-list { height: 1fr; overflow-y: auto; }
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.cfg            = config
        self.db_path        = config.db_path
        self.tags           = config.tags
        self._we_tags       = (
            config.tags.by_category("weekend") + config.tags.by_category("any")
        )
        self._tag_idx       = 0
        self._projects: list[db.Project] = []
        self._project_idx   = 0
        self._entries: list[db.LogEntry] = []
        self._todos:   list[db.Todo]     = []
        self._todo_idx: int              = 0

    # ── Sichere UI-Helfer ─────────────────────────────────────────────────────

    def _q(self, selector: str, widget_type=None):
        try:
            return self.query_one(selector, widget_type) if widget_type else self.query_one(selector)
        except Exception:
            return None

    def _update(self, selector: str, widget_type, content: str) -> None:
        w = self._q(selector, widget_type)
        if w is not None:
            try:
                w.update(content)
            except Exception:
                pass

    def _add_class(self, selector: str, css_class: str) -> None:
        w = self._q(selector)
        if w is not None:
            try: w.add_class(css_class)
            except Exception: pass

    def _remove_class(self, selector: str, css_class: str) -> None:
        w = self._q(selector)
        if w is not None:
            try: w.remove_class(css_class)
            except Exception: pass

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main-split"):
            with Vertical(id="project-panel"):
                yield Label("  🔨 PROJEKTE", id="project-title-bar")
                with ScrollableContainer(id="project-list"):
                    yield Static("", id="project-list-content")
            with Vertical(id="log-panel"):
                yield Label("", id="log-title-bar")
                with ScrollableContainer(id="log-list"):
                    yield Static("", id="log-content")
                with Horizontal(id="input-row"):
                    yield Label("", id="tag-selector")
                    yield LogInput(placeholder="Was hast du gemacht? (Tab = Tag)", id="log-input")
            with Vertical(id="todo-panel"):
                yield Label("", id="todo-panel-title")
                with ScrollableContainer(id="todo-list"):
                    yield Static("", id="todo-list-content")
        yield Footer()

    # ── Mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._load_all()
        self._update_tag_selector()
        self._tick_title()

    # ── Laden ─────────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._load_projects()
        self._load_log()
        self._load_todos()

    def _load_projects(self) -> None:
        self._projects = db.project_list(self.db_path, phase="active")
        # planning auch anzeigen
        planning = db.project_list(self.db_path, phase="planning")
        all_p = self._projects + planning
        # Deduplizieren
        seen = set()
        merged = []
        for p in all_p:
            if p.id not in seen:
                merged.append(p)
                seen.add(p.id)
        self._projects = merged
        self._project_idx = min(self._project_idx, max(0, len(self._projects) - 1))
        self._render_projects()

    def _render_projects(self) -> None:
        if not self._projects:
            content = "[dim]  Keine aktiven Projekte\n  [p] Neues Projekt anlegen[/]"
            self._update("#project-list-content", Static, content)
            return

        lines = []
        for i, p in enumerate(self._projects):
            sym, col = PHASE_BADGES.get(p.phase, ("·", "#888888"))
            tag = self.tags.get(p.tag_key) if p.tag_key else None
            tag_s = f"  [{tag.color}]{tag.symbol}[/]" if tag else ""

            if i == self._project_idx:
                lines.append(
                    f"[bold #C8A165]▶  [{col}]{sym}[/]  {p.name}{tag_s}[/]"
                )
            else:
                lines.append(
                    f"[dim]   [{col}]{sym}[/]  {p.name}{tag_s}[/dim]"
                )
            lines.append("")

        self._update("#project-list-content", Static, "\n".join(lines))
        self._update_log_title()

    def _load_log(self) -> None:
        self._entries = db.log_get_day(self.db_path, mode="weekend")
        self._render_log()
        self._update_log_title()

    def _render_log(self) -> None:
        if not self._entries:
            content = "[dim]  Noch nichts geloggt heute.\n  Fang einfach an.[/]"
        else:
            lines = []
            for e in self._entries:
                tag = self.tags.get(e.tag_key)
                sym = tag.symbol if tag else "·"
                col = tag.color  if tag else "#888888"
                pad = 7 - (_sym_w(sym) - 1)
                lines.append(
                    f"[dim]{_fmt_time(e.created_at)}[/]  "
                    f"[bold {col}]{sym} {e.tag_key:<{pad}}[/]  "
                    f"{escape(e.content)}"
                )
            content = "\n".join(lines)

        self._update("#log-content", Static, content)
        try:
            (lambda w: w.scroll_end(animate=False) if w else None)(self._q("#log-list", ScrollableContainer))
        except Exception:
            pass

    def _update_log_title(self) -> None:
        proj_name = ""
        if self._projects:
            proj_name = f"  ·  {self._projects[self._project_idx].name}"
        self._update("#log-title-bar", Label,
            f"  📋 LOG{proj_name}  ·  {date.today().strftime('%A, %d. %b')}  ·  {len(self._entries)} Einträge"
        )

    # ── Todo-Methoden ─────────────────────────────────────────────────────────

    def _load_todos(self) -> None:
        current_id = self._todos[self._todo_idx].id if self._todos else None
        self._todos = db.todo_list(self.db_path, mode="weekend")
        # Status-Bucket: active zuerst, dann open/paused, dann done/dropped.
        self._todos.sort(key=lambda t: (
            0 if t.status == "active"
            else 1 if t.status in ("open", "paused")
            else 2,
            t.created_at,
        ))
        if current_id is not None:
            ids = [t.id for t in self._todos]
            self._todo_idx = ids.index(current_id) if current_id in ids else 0
        self._render_todos()
        self._update_todo_panel_title()

    def _render_todos(self) -> None:
        if not self._todos:
            self._update("#todo-list-content", Static,
                         "[dim]  (keine Todos – [a] anlegen)[/]")
            return

        self._todo_idx = max(0, min(self._todo_idx, len(self._todos) - 1))
        lines = []
        for i, todo in enumerate(self._todos):
            selected = (i == self._todo_idx)
            icon = _STATUS_ICONS.get(todo.status, "○")
            dim  = todo.status in ("done", "dropped")
            tc   = "#444466" if dim else "#C8C8C8"
            title_s = escape(todo.title[:36])

            if selected:
                line1 = f"[bold #C8A165]▶[/] {icon}  [bold reverse {tc}] {title_s} [/]"
                line2 = "     [dim][d] Done  [x] Löschen[/]"
                lines += [line1, line2, ""]
            else:
                lines += [f"  {icon}  [bold {tc}]{title_s}[/]", ""]

        self._update("#todo-list-content", Static, "\n".join(lines))

    def _update_todo_panel_title(self) -> None:
        active = sum(1 for t in self._todos if t.status in ("open", "active", "paused"))
        done   = sum(1 for t in self._todos if t.status == "done")
        self._update("#todo-panel-title", Label,
                     f"  ✅ TODOS  ·  {active} offen  ·  {done} done")

    # ── Tag-Selector ──────────────────────────────────────────────────────────

    def _update_tag_selector(self) -> None:
        if not self._we_tags:
            return
        # Standard-Tag aus dem aktiven Projekt ableiten
        if self._projects:
            proj = self._projects[self._project_idx]
            if proj.tag_key:
                proj_tags = [t for t in self._we_tags if t.key == proj.tag_key]
                if proj_tags:
                    # Tag-Index auf Projekt-Tag setzen wenn noch auf Default
                    idx_for_proj = self._we_tags.index(proj_tags[0])
                    if self._tag_idx == 0:
                        self._tag_idx = idx_for_proj

        tag = self._we_tags[self._tag_idx]
        self._update("#tag-selector", Label,
            f"[bold {tag.color}] {tag.symbol} {tag.key} [/]"
        )

    def action_next_tag(self) -> None:
        if self._we_tags:
            self._tag_idx = (self._tag_idx + 1) % len(self._we_tags)
            self._update_tag_selector()

    def action_prev_tag(self) -> None:
        if self._we_tags:
            self._tag_idx = (self._tag_idx - 1) % len(self._we_tags)
            self._update_tag_selector()

    # ── Projekt-Navigation ────────────────────────────────────────────────────

    def action_next_project(self) -> None:
        if self._projects:
            self._project_idx = (self._project_idx + 1) % len(self._projects)
            self._tag_idx = 0
            self._render_projects()
            self._update_tag_selector()

    def action_prev_project(self) -> None:
        if self._projects:
            self._project_idx = (self._project_idx - 1) % len(self._projects)
            self._tag_idx = 0
            self._render_projects()
            self._update_tag_selector()

    def action_new_project(self) -> None:
        weekend_tags = self.tags.by_category("weekend")

        def on_result(result: dict | None) -> None:
            if not result:
                return
            db.project_add(self.db_path, name=result["name"], tag_key=result["tag_key"])
            self._load_projects()
            self.notify(f"Projekt '{result['name']}' angelegt.", timeout=2)

        self.push_screen(NewProjectModal(weekend_tags), on_result)

    def action_done_project(self) -> None:
        if not self._projects:
            return
        proj = self._projects[self._project_idx]
        db.project_set_phase(self.db_path, proj.id, "done")
        self._load_projects()
        self.notify(f"'{proj.name}' abgeschlossen! ✓", timeout=2)

    # ── Todo-Actions ──────────────────────────────────────────────────────────

    def action_todo_up(self) -> None:
        if self._todos and self._todo_idx > 0:
            self._todo_idx -= 1
            self._render_todos()

    def action_todo_down(self) -> None:
        if self._todos and self._todo_idx < len(self._todos) - 1:
            self._todo_idx += 1
            self._render_todos()

    def action_todo_done(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status in ("done", "dropped"):
            self.notify(f"Bereits abgeschlossen: {todo.title[:40]}", timeout=2)
            return
        db.todo_set_status(self.db_path, todo.id, "done")
        self._load_todos()
        self.notify(f"✓  {todo.title[:40]}", timeout=2)

    def action_todo_delete(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        db.todo_delete(self.db_path, todo.id)
        self._todo_idx = max(0, self._todo_idx - 1)
        self._load_todos()
        self.notify(f"✗  '{todo.title[:40]}' gelöscht", timeout=2)

    def action_add_todo(self) -> None:
        from ..widgets.new_todo import NewTodoModal

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
            self._load_todos()
            self.notify(f"Todo angelegt: {result['title'][:40]}", timeout=2)

        self.push_screen(NewTodoModal(default_mode="weekend"), on_result)

    # ── Log-Eingabe ───────────────────────────────────────────────────────────

    def action_focus_input(self) -> None:
        (lambda w: w.focus() if w else None)(self._q("#log-input", LogInput))

    @on(LogInput.TagNext)
    def on_tag_next(self, _) -> None:
        self.action_next_tag()

    @on(LogInput.TagPrev)
    def on_tag_prev(self, _) -> None:
        self.action_prev_tag()

    @on(Input.Submitted, "#log-input")
    def log_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or not self._we_tags:
            return
        tag_key = self._we_tags[self._tag_idx].key
        db.log_add(self.db_path, tag_key=tag_key, content=text, mode="weekend")
        event.input.clear()
        self._load_log()

    # ── Wochenrückblick ───────────────────────────────────────────────────────

    def action_show_week(self) -> None:
        from ..views.weekly import WeeklyScreen
        today = date.today()
        iso = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]}"
        self.push_screen(WeeklyScreen(self.db_path, self.tags, iso))

    # ── Modus wechseln ───────────────────────────────────────────────────────

    def action_goto_work(self) -> None:
        self.exit("work")

    def action_goto_family(self) -> None:
        self.exit("family")

    def action_goto_weekend(self) -> None:
        self.exit("weekend")

    # ── Refresh + Uhr ─────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._load_all()

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
            return proc.returncode, (out + err).decode(errors="replace")

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

    @work(exclusive=True)
    async def _tick_title(self) -> None:
        while True:
            now = datetime.now()
            self.title = (
                f"tui-log  ·  WOCHENENDE  ·  "
                f"{now.strftime('%A, %d. %b')}  ·  {now.strftime('%H:%M')}"
            )
            await asyncio.sleep(60)

def run_weekend_mode(config: AppConfig) -> None:
    WeekendApp(config).run()
