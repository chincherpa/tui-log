"""
tui_log/views/weekly.py
~~~~~~~~~~~~~~~~~~~~~~~
Wochenrückblick – als Screen aus der Work-App pushbar.

Layout:
  ┌─ Header: KW 14 · 28. Mär – 03. Apr ─────────────────────── ┐
  │                                                              │
  │  ARBEIT                                                      │
  │  5 Arbeitstage                                               │
  │  Ø Energie ●●●○○                                             │
  │  12 done · 2 offen                                           │
  │  Top-Tags: ...                                               │
  │                                                              │
  │  HIGHLIGHTS                                                  │
  │                                                              │
  │  TAGESBEWERTUNGEN          FOKUS-ZEIT                       │
  │  Mo ● Di ● Mi ~ Do ● Fr ●  4h 23m                          │
  │                                                              │
  ├─ [←] Vorwoche  [→] Nächste  [Enter/q] Zurück ──────────────┤

Navigation: ← → zwischen Wochen
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

from .. import db_utils as db

# ── Helfer ────────────────────────────────────────────────────────────────────

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

def _week_date_range(iso_week: str) -> tuple[date, date]:
    year, week = iso_week.split("-W")
    monday = date.fromisocalendar(int(year), int(week), 1)
    return monday, monday + timedelta(days=6)

def _iso_week(d: date) -> str:
    c = d.isocalendar()
    return f"{c[0]}-W{c[1]}"

def _prev_week(iso_week: str) -> str:
    monday, _ = _week_date_range(iso_week)
    return _iso_week(monday - timedelta(days=7))

def _next_week(iso_week: str) -> str:
    monday, _ = _week_date_range(iso_week)
    return _iso_week(monday + timedelta(days=7))

RATING_DISPLAY = {
    "zaeh":     ("~",  "#FF6B6B"),
    "ok":       ("◎",  "#FFD93D"),
    "gut":      ("●",  "#00C896"),
    "sehr_gut": ("★",  "#4FC3F7"),
}

WEEKDAYS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# ── WeeklyScreen ─────────────────────────────────────────────────────────────

class WeeklyScreen(Screen):

    BINDINGS = [
        Binding("left,h",       "prev_week",  "← Vorwoche",   show=True),
        Binding("right,l",      "next_week",  "Nächste →",    show=True),
        Binding("escape,q,enter","pop",        "Zurück",       show=True),
    ]

    DEFAULT_CSS = """
    WeeklyScreen    { background: #0D0D1A; color: #C8C8C8; }
    Header          { background: #0D1A1A; color: #4FC3F7; height: 1; }
    Footer          { background: #0D1A1A; color: #555577; height: 1; }

    #week-scroll    { height: 1fr; padding: 1 2; }

    .section-title  { color: #4FC3F7; text-style: bold; height: 1; margin-top: 1; }
    .divider        { color: #1A2A2A; height: 1; }

    #top-split      { layout: horizontal; height: auto; margin-bottom: 1; }
    #work-col       { width: 1fr; padding-right: 2; }

    .stat-label     { color: #888899; height: 1; }
    .stat-value     { color: #C8C8C8; height: 1; }
    .stat-highlight { color: #00C896; height: 1; text-style: bold; }

    #highlights-list { height: auto; }
    .highlight-line  { color: #FFD93D; height: 1; }

    #days-row       { layout: horizontal; height: 1; margin-top: 1; }
    .day-cell       { width: 1fr; content-align: center middle; }

    #focus-bar      { height: 1; margin-top: 1; }

    #week-note-label { color: #C8C8C8; text-style: bold; height: 1; margin-top: 1; }
    #week-note      { color: #888899; height: auto; }
    """

    def __init__(self, db_path: Path, tags, iso_week: str) -> None:
        super().__init__()
        self.db_path  = db_path
        self.tags     = tags
        self._week    = iso_week
        self._summary: db.WeekSummary | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with ScrollableContainer(id="week-scroll"):
            yield Static("", id="week-content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_and_render()

    def _load_and_render(self) -> None:
        self._summary = db.week_summary(self.db_path, self._week)
        monday, sunday = _week_date_range(self._week)
        _, week_num = self._week.split("-W")
        self.title = (
            f"tui-log  ·  KW {week_num}  ·  "
            f"{monday.strftime('%d. %b')} – {sunday.strftime('%d. %b %Y')}"
        )
        content = self._build_content(self._summary, monday, sunday)
        self.query_one("#week-content", Static).update(content)

    def _build_content(self, s: db.WeekSummary, monday: date, sunday: date) -> str:
        _, week_num = self._week.split("-W")
        today = date.today()
        is_current = _iso_week(today) == self._week

        lines: list[str] = []

        # ── Kopf ─────────────────────────────────────────────────────────────
        lines.append(
            f"[bold #4FC3F7]KW {week_num}[/]  ·  "
            f"{monday.strftime('%d. %b')} – {sunday.strftime('%d. %b %Y')}"
            + (" [dim](diese Woche)[/]" if is_current else "")
        )
        lines.append("[#1A2A2A]" + "─" * 60 + "[/]")
        lines.append("")

        done_cnt  = s.log_counts.get("done",  0)
        fix_cnt   = s.log_counts.get("fix",   0)
        idea_cnt  = s.log_counts.get("idea",  0)
        block_cnt = s.log_counts.get("block", 0)

        lines.append(
            f"  [dim]Arbeitstage:[/]  [bold]{s.work_days}[/]     "
            f"[dim]Energie:[/]  [#00C896]{_energy_dots(s.avg_energy)}[/]"
        )
        lines.append(
            f"  [#00C896]✓ {done_cnt} done[/]  "
            f"[#FFD93D]⚡ {fix_cnt} fix[/]  "
            f"[#C77DFF]💡 {idea_cnt} ideas[/]  "
            f"[#FF6B6B]✕ {block_cnt} blocks[/]"
        )

        # Top-Tags
        if s.top_tags:
            top_str = "  ".join(
                f"[dim]{k}[/] [bold]{v}×[/]"
                for k, v in s.top_tags[:5]
            )
            lines.append(f"  [dim]Top:[/]  {top_str}")

        # Focus-Zeit
        lines.append(
            f"  [dim]Focus-Zeit:[/]  [bold #4FC3F7]{_fmt_duration(s.focus_total_s)}[/]"
        )
        lines.append("")

        # ── Tagesbewertungen ─────────────────────────────────────────────────
        lines.append("[bold #C8C8C8]TAGESBEWERTUNGEN[/]")
        day_metas = db.day_get_week(self.db_path, self._week)
        meta_by_date = {m.date: m for m in day_metas}

        rating_row = []
        for i in range(7):
            d = monday + timedelta(days=i)
            meta = meta_by_date.get(d.isoformat())
            day_name = WEEKDAYS_SHORT[i]
            if meta and meta.day_rating:
                sym, col = RATING_DISPLAY.get(meta.day_rating, ("·", "#888888"))
                rating_row.append(f"[{col}]{day_name} {sym}[/]")
            elif d <= today:
                rating_row.append(f"[dim]{day_name} ·[/]")
            else:
                rating_row.append(f"[dim]{day_name}  [/]")

        lines.append("  " + "   ".join(rating_row))

        # Carry-over
        if s.open_blocks > 0:
            lines.append(
                f"  [#FF6B6B]✕ {s.open_blocks} Block(s) noch offen[/]"
            )
        lines.append("")

        # ── Highlights ([high]-Einträge) ─────────────────────────────────────
        highlights = db.log_get_range(
            self.db_path,
            date_from=monday.isoformat(),
            date_to=sunday.isoformat(),
            tag_key="high",
        )
        if highlights:
            lines.append("[bold #FFD93D]HIGHLIGHTS[/]")
            for h in highlights:
                weekday = WEEKDAYS_SHORT[date.fromisoformat(h.date).weekday()]
                lines.append(f"  [#FFD93D]★[/]  [dim]{weekday}[/]  {h.content}")
            lines.append("")

        # ── Wochennotizen (evening_note der Arbeitstage) ──────────────────────
        notes = [
            (m.date, m.evening_note)
            for m in day_metas
            if m.evening_note
        ]
        if notes:
            lines.append("[bold #888899]NOTIZEN[/]")
            for d_str, note in notes:
                weekday = WEEKDAYS_SHORT[date.fromisoformat(d_str).weekday()]
                lines.append(f"  [dim]{weekday}[/]  {note[:70]}")
            lines.append("")

        # ── Morgen-Fokus der Arbeitstage ─────────────────────────────────────
        focuses = [
            (m.date, m.morning_focus)
            for m in day_metas
            if m.morning_focus and m.mode == "work"
        ]
        if focuses:
            lines.append("[bold #888899]FOKUS DER WOCHE[/]")
            for d_str, focus in focuses:
                weekday = WEEKDAYS_SHORT[date.fromisoformat(d_str).weekday()]
                lines.append(f"  [dim]{weekday}[/]  [#5B8DEF]{focus[:60]}[/]")

        return "\n".join(lines)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_prev_week(self) -> None:
        self._week = _prev_week(self._week)
        self._load_and_render()

    def action_next_week(self) -> None:
        next_w = _next_week(self._week)
        # Nicht in die Zukunft navigieren
        today_w = _iso_week(date.today())
        if next_w > today_w:
            self.notify("Das ist die aktuelle Woche.", timeout=1)
            return
        self._week = next_w
        self._load_and_render()

    def action_pop(self) -> None:
        self.app.pop_screen()
