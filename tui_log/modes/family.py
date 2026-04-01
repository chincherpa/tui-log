"""
tui_log/modes/family.py
~~~~~~~~~~~~~~~~~~~~~~~
Familien-Modus – nach 15 Uhr und am Abend.

Layout:
  ┌─ Header: PRIVAT · Uhrzeit ─────────────────────────────────┐
  │  Arbeits-Zusammenfassung (klappbar, gedimmt)               │
  │  ─────────────────────────────────────────────             │
  │  Familien-Log (scrollbar, freier Text)                     │
  │  [Tag] Eingabe-Leiste                                      │
  ├─ Footer: Keybindings ──────────────────────────────────────┤

Tags: hannah, elliot, high, schwer, note
Kein Stress, keine Struktur-Zwänge.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, Static
from textual import on, work

from rich.markup import escape

from ..config import AppConfig
from .. import db_utils as db
from ..widgets.log_input import LogInput

# ── Helfer ────────────────────────────────────────────────────────────────────

def _fmt_time(iso_dt: str) -> str:
    try:
        return iso_dt[11:16]
    except Exception:
        return "??:??"

def _evening_greeting() -> str:
    h = datetime.now().hour
    if h < 17:
        return "Schönen Nachmittag"
    if h < 20:
        return "Schönen Abend"
    return "Gute Nacht"

# ── Feierabend-Modal (einfach) ────────────────────────────────────────────────

from textual.screen import ModalScreen

RATINGS = ["zaeh", "ok", "gut", "sehr_gut"]
RATING_DISPLAY = {
    "zaeh":     "~ zäh",
    "ok":       "◎ ok",
    "gut":      "● gut",
    "sehr_gut": "★ sehr gut",
}

class EveningModal(ModalScreen[dict | None]):
    """Kurzes Abend-Ritual: Was war schön? Wie war der Tag?"""

    BINDINGS = [Binding("escape", "cancel", "Überspringen")]

    def __init__(self, open_items: str = "") -> None:
        super().__init__()
        self._rating_idx = 2   # Default: "gut"
        self._open_items = open_items

    def compose(self) -> ComposeResult:
        with Vertical(id="evening-dialog"):
            yield Label("🌙  Tagesabschluss", id="evening-title")
            yield Label("Was war heute schön?", classes="evening-label")
            yield LogInput(placeholder="Highlight des Tages…", id="evening-highlight", classes="evening-input")
            yield Label("Noch offen für morgen?", classes="evening-label")
            yield Input(
                value=self._open_items,
                placeholder="(leer lassen wenn nichts offen)",
                id="evening-open",
                classes="evening-input",
            )
            yield Label("Wie war der Tag?", classes="evening-label")
            yield Label(self._rating_str(), id="evening-rating")
            yield Label("[←/→] Bewertung  [Enter] Fertig  [Esc] Überspringen", id="evening-hint")

    DEFAULT_CSS = """
    EveningModal { align: center middle; }
    #evening-dialog {
        background: #1A0D1A;
        border: solid #C77DFF;
        width: 60;
        height: auto;
        padding: 1 2;
    }
    #evening-title  { color: #C77DFF; text-style: bold; height: 1; margin-bottom: 1; }
    .evening-label  { color: #C8C8C8; text-style: bold; height: 1; }
    .evening-input  { background: #2A1A2A; color: #E8E8E8; border: solid #3A2A3A; margin-bottom: 1; }
    .evening-input:focus { border: solid #C77DFF; }
    #evening-rating { color: #C77DFF; text-style: bold; height: 1; margin-bottom: 1; }
    #evening-hint   { color: #555577; height: 1; }
    """

    def _rating_str(self) -> str:
        parts = []
        for i, r in enumerate(RATINGS):
            label = RATING_DISPLAY[r]
            parts.append(f"[{label}]" if i == self._rating_idx else label)
        return "  " + "   ".join(parts)

    def _update_rating(self) -> None:
        self._update("#evening-rating", Label, self._rating_str())

    def on_key(self, event) -> None:
        if event.key == "left" and self._rating_idx > 0:
            self._rating_idx -= 1
            self._update_rating()
            event.stop()
        elif event.key == "right" and self._rating_idx < len(RATINGS) - 1:
            self._rating_idx += 1
            self._update_rating()
            event.stop()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        # Beim ersten Feld: Tab zum nächsten
        if event.input.id == "evening-highlight":
            (lambda w: w.focus() if w else None)(self._q("#evening-open", Input))
            return
        # Beim zweiten Feld: Abschließen
        highlight = self.query_one("#evening-highlight", Input).value.strip()
        open_val  = self.query_one("#evening-open", Input).value.strip()
        self.dismiss({
            "highlight":  highlight,
            "open_items": open_val,
            "rating":     RATINGS[self._rating_idx],
        })

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        (lambda w: w.focus() if w else None)(self._q("#evening-highlight", Input))

# ── Haupt-App ─────────────────────────────────────────────────────────────────

class FamilyApp(App):

    BINDINGS = [
        Binding("space,n", "focus_input",    "Log",       show=True),
        Binding("tab",     "next_tag",       "Tag",       show=False),
        Binding("shift+tab","prev_tag",      "Tag",       show=False),
        Binding("e",       "evening_ritual", "Abend",     show=True),
        Binding("w",       "show_week",      "Woche",     show=True),
        Binding("r",       "refresh",        "Refresh",   show=False),
        Binding("ctrl+a",     "goto_work",    "→ Arbeit",    show=True),
        Binding("ctrl+f",     "goto_family",  "→ Familie",   show=True),
        Binding("ctrl+w",     "goto_weekend", "→ Wochenende",show=True),
        Binding("q",       "quit",           "Beenden",   show=True),
    ]

    DEFAULT_CSS = """
    Screen          { background: #0D0D1A; color: #C8C8C8; }
    Header          { background: #1A0D1A; color: #C77DFF; height: 1; }
    Footer          { background: #1A0D1A; color: #555577; height: 1; }

    #work-summary {
        height: auto;
        max-height: 6;
        background: #0D0D0D;
        border: solid #1A1A2E;
        padding: 0 1;
        margin-bottom: 0;
        color: #444466;
    }
    #work-summary-title { color: #333355; text-style: bold; height: 1; }

    #family-panel   { height: 1fr; border: solid #2A1A2A; padding: 0 1; }
    #family-panel:focus-within { border: solid #C77DFF; }
    #panel-title    { background: #1A0D1A; color: #C77DFF; height: 1; padding: 0 1; text-style: bold; }

    #log-list       { height: 1fr; overflow-y: auto; }

    #input-row      { height: 3; layout: horizontal; background: #1A0D1A; border-top: solid #2A1A2A; padding: 0 1; align: left middle; }
    #tag-selector   { width: auto; min-width: 12; height: 1; background: #2A1A2A; color: #C77DFF; text-style: bold; padding: 0 1; margin-right: 1; }
    #log-input      { width: 1fr; height: 1; background: #1A0D1A; color: #E8E8E8; border: none; }
    #log-input:focus{ border: none; background: #1A0D1A; }
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.cfg        = config
        self.db_path    = config.db_path
        self.tags       = config.tags
        self._fam_tags  = (
            config.tags.by_category("family") + config.tags.by_category("any")
        )
        self._tag_idx   = 0
        self._entries: list[db.LogEntry] = []

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

        # Arbeits-Zusammenfassung (gedimmt, oben)
        with Vertical(id="work-summary"):
            yield Label("── Heute bei der Arbeit ─────────────────────", id="work-summary-title")
            yield Static("", id="work-summary-content")

        with Vertical(id="family-panel"):
            yield Label("", id="panel-title")
            with ScrollableContainer(id="log-list"):
                yield Static("", id="log-content")
            with Horizontal(id="input-row"):
                yield Label("", id="tag-selector")
                yield LogInput(placeholder="Was passiert? (Tab = Tag)", id="log-input")

        yield Footer()

    # ── Mount ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._load_all()
        self._update_tag_selector()
        self._tick_title()

    # ── Laden ─────────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        self._load_work_summary()
        self._load_family_log()
        self._update_panel_title()

    def _load_work_summary(self) -> None:
        work_entries = db.log_get_day(self.db_path, mode="work")
        meta         = db.day_get(self.db_path)

        lines = []
        if meta and meta.morning_focus:
            lines.append(f"[dim]  Fokus war: {meta.morning_focus}[/]")
        for e in work_entries[-6:]:
            tag = self.tags.get(e.tag_key)
            sym = tag.symbol if tag else "·"
            col = tag.color  if tag else "#444466"
            lines.append(
                f"[dim]{_fmt_time(e.created_at)}[/]  "
                f"[{col}]{sym} {e.tag_key:<7}[/]  "
                f"[dim]{escape(e.content[:50])}[/]"
            )
        if not lines:
            lines = ["[dim]  (keine Arbeitseinträge heute)[/]"]

        self._update("#work-summary-content", Static, "\n".join(lines))

    def _load_family_log(self) -> None:
        self._entries = db.log_get_day(self.db_path, mode="family")
        self._render_log()

    def _render_log(self) -> None:
        if not self._entries:
            greeting = _evening_greeting()
            content = f"[dim]  {greeting}. Schreib einfach drauf los.[/]"
        else:
            lines = []
            for e in self._entries:
                tag = self.tags.get(e.tag_key)
                sym = tag.symbol if tag else "·"
                col = tag.color  if tag else "#888888"
                lines.append(
                    f"[dim]{_fmt_time(e.created_at)}[/]  "
                    f"[bold {col}]{sym} {e.tag_key:<8}[/]  "
                    f"{escape(e.content)}"
                )
            content = "\n".join(lines)

        self._update("#log-content", Static, content)
        try:
            (lambda w: w.scroll_end(animate=False) if w else None)(self._q("#log-list", ScrollableContainer))
        except Exception:
            pass

    def _update_panel_title(self) -> None:
        cnt = len(self._entries)
        self._update("#panel-title", Label, 
            f"  🏠 PRIVAT  ·  {date.today().strftime('%A, %d. %b')}  ·  {cnt} Einträge"
        )

    # ── Tag-Selector ──────────────────────────────────────────────────────────

    def _update_tag_selector(self) -> None:
        if not self._fam_tags:
            return
        tag = self._fam_tags[self._tag_idx]
        self._update("#tag-selector", Label, 
            f"[bold {tag.color}] {tag.symbol} {tag.key} [/]"
        )

    def action_next_tag(self) -> None:
        if self._fam_tags:
            self._tag_idx = (self._tag_idx + 1) % len(self._fam_tags)
            self._update_tag_selector()

    def action_prev_tag(self) -> None:
        if self._fam_tags:
            self._tag_idx = (self._tag_idx - 1) % len(self._fam_tags)
            self._update_tag_selector()

    # ── Eingabe ───────────────────────────────────────────────────────────────

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
        if not text or not self._fam_tags:
            return
        tag_key = self._fam_tags[self._tag_idx].key
        db.log_add(self.db_path, tag_key=tag_key, content=text, mode="family")
        event.input.clear()
        self._load_family_log()
        self._update_panel_title()

    # ── Abend-Ritual ──────────────────────────────────────────────────────────

    def action_evening_ritual(self) -> None:
        meta = db.day_get(self.db_path)
        open_carry = meta.evening_open if (meta and meta.evening_open) else ""

        def on_result(result: dict | None) -> None:
            if not result:
                return
            # Highlight als Log-Eintrag speichern
            if result["highlight"]:
                db.log_add(
                    self.db_path,
                    tag_key="high",
                    content=result["highlight"],
                    mode="family",
                )
            # DayMeta Abend setzen
            db.day_set_evening(
                self.db_path,
                done=result["highlight"] or "–",
                open_items=result["open_items"],
                rating=result["rating"],
            )
            self._load_all()
            self.notify("Tagesabschluss gespeichert. Gute Nacht! 🌙", timeout=3)

        self.push_screen(EveningModal(open_carry), on_result)

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

    @work(exclusive=True)
    async def _tick_title(self) -> None:
        while True:
            now = datetime.now()
            self.title = (
                f"tui-log  ·  PRIVAT  ·  "
                f"{now.strftime('%A, %d. %b')}  ·  {now.strftime('%H:%M')}"
            )
            await asyncio.sleep(60)

def run_family_mode(config: AppConfig) -> None:
    FamilyApp(config).run()
