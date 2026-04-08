"""
tui_log/widgets/focus.py
~~~~~~~~~~~~~~~~~~~~~~~~
Focus-Session Modal – bewusst minimal und kompatibel gehalten.
"""

from __future__ import annotations

from datetime import datetime
from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static
from textual.containers import Vertical
from textual import on


TIMER_PRESETS = [25, 45, 90, 0]   # 0 = offen
PRESET_LABELS = ["25 min", "45 min", "90 min", "Offen"]
OUTCOME_LABELS = {"solved": "Gelöst ✓", "open": "Weiter offen", "blocked": "Blockiert ✕"}


def _build_timer_str(elapsed: int, preset_idx: int) -> str:
    """Einfacher Timer-String ohne dynamische Progress-Bar."""
    h = elapsed // 3600
    m = (elapsed % 3600) // 60
    s = elapsed % 60
    preset = TIMER_PRESETS[preset_idx]
    if preset > 0:
        total_s = preset * 60
        remaining = max(0, total_s - elapsed)
        rm, rs = remaining // 60, remaining % 60
        return f"  Laufzeit {h:02d}:{m:02d}:{s:02d}  Rest {rm:02d}:{rs:02d}  ({PRESET_LABELS[preset_idx]})"
    return f"  Laufzeit {h:02d}:{m:02d}:{s:02d}  ({PRESET_LABELS[preset_idx]})"


def _build_preset_bar(preset_idx: int) -> str:
    parts = []
    for i, label in enumerate(PRESET_LABELS):
        parts.append(f">{label}<" if i == preset_idx else label)
    return "  " + "  ·  ".join(parts)


class FocusModal(ModalScreen[dict | None]):
    """
    Rückgabe: {outcome, elapsed_s, notes, preset, log_entry} oder None bei Minimieren.
    """

    BINDINGS = [
        Binding("escape",  "minimize",     "Minimieren"),
        Binding("ctrl+s",  "stop_session", "Session beenden"),
    ]

    def __init__(self, todo, context_entries: list) -> None:
        super().__init__()
        self.todo        = todo
        self.ctx_entries = context_entries
        self._preset_idx = 1        # Default: 45 min
        self._notes: list[tuple[str, str]] = []
        self._running = True
        self._outcome  = "open"
        self._started_at = datetime.now()

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="focus-dialog"):
            yield Label(escape(self.todo.title), id="focus-todo-title")
            yield Label(escape(self.todo.context or ""), id="focus-todo-context")

            yield Label(_build_timer_str(0, self._preset_idx), id="focus-timer-display")
            yield Label(_build_preset_bar(self._preset_idx), id="focus-timer-bar")

            yield Label("── Notizen ──────────────────────────────", id="focus-notes-label")
            with Vertical(id="focus-notes-list"):
                yield Static("", id="focus-notes-content")

            yield Input(placeholder="Notiz einwerfen…", id="focus-note-input")

            if self.ctx_entries:
                yield Label("── Kontext ──────────────────────────────", id="focus-context-label")
                with Vertical(id="focus-context-list"):
                    for entry in self.ctx_entries[-4:]:
                        ts = entry.created_at[11:16]
                        yield Label(
                            f"  {entry.date} {ts}  ({escape(entry.tag_key)})  {escape(entry.content[:45])}",
                            classes="focus-context-line",
                        )

            yield Label(
                "Tab Preset  Ctrl+S Beenden  Esc Minimieren",
                id="focus-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#focus-note-input", Input).focus()

    # ── Notizen ───────────────────────────────────────────────────────────────

    def _refresh_notes(self) -> None:
        lines = []
        for t, c in self._notes:
            lines.append(f"  {t}  {escape(c)}")
        content = "\n".join(lines) if lines else "  (noch keine Notizen)"
        try:
            self.query_one("#focus-notes-content", Static).update(content)
        except Exception:
            pass

    @on(Input.Submitted, "#focus-note-input")
    def note_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            ts = datetime.now().strftime("%H:%M")
            self._notes.append((ts, text))
            event.input.clear()
            self._refresh_notes()

    # ── Keys ──────────────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        # Tab: Timer-Preset wechseln
        if event.key == "tab":
            self._preset_idx = (self._preset_idx + 1) % len(TIMER_PRESETS)
            try:
                elapsed = max(0, int((datetime.now() - self._started_at).total_seconds()))
                self.query_one("#focus-timer-bar", Label).update(_build_preset_bar(self._preset_idx))
                self.query_one("#focus-timer-display", Label).update(_build_timer_str(elapsed, self._preset_idx))
            except Exception:
                pass
            event.stop()

        elif event.key == "1":
            self._outcome = "solved";   self._show_outcome()
        elif event.key == "2":
            self._outcome = "open";     self._show_outcome()
        elif event.key == "3":
            self._outcome = "blocked";  self._show_outcome()

    def _show_outcome(self) -> None:
        label = OUTCOME_LABELS[self._outcome]
        try:
            self.query_one("#focus-hint", Label).update(
                f"Outcome: {label}  |  Ctrl+S Beenden  Tab Preset  1/2/3 Outcome"
            )
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_minimize(self) -> None:
        self._running = False
        self.dismiss(None)

    def action_stop_session(self) -> None:
        self._running = False
        elapsed = max(0, int((datetime.now() - self._started_at).total_seconds()))
        self.dismiss({
            "outcome":   self._outcome,
            "elapsed_s": elapsed,
            "notes":     [c for _, c in self._notes],
            "preset":    PRESET_LABELS[self._preset_idx],
            "log_entry": "",
        })
