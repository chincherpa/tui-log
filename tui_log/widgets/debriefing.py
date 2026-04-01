"""
tui_log/widgets/debriefing.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Debriefing nach einer Focus-Session.
Fragt nach Outcome + Log-Eintrag, schreibt beides automatisch.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical
from textual import on

OUTCOME_OPTIONS = ["solved", "open", "blocked"]
OUTCOME_DISPLAY = {
    "solved":  "✓  Gelöst",
    "open":    "↻  Weiter offen",
    "blocked": "✕  Blockiert",
}

def _fmt_duration(seconds: int) -> str:
    m = seconds // 60
    h = m // 60
    rm = m % 60
    if h == 0:
        return f"{m} min"
    return f"{h}h {rm:02d}min"

class DebriefingModal(ModalScreen[dict | None]):
    """
    Rückgabe: {outcome, log_entry} oder None bei Abbruch.
    """

    BINDINGS = [Binding("escape", "cancel", "Abbrechen")]

    def __init__(self, todo_title: str, elapsed_s: int, suggested_outcome: str) -> None:
        super().__init__()
        self.todo_title = todo_title
        self.elapsed_s  = elapsed_s
        self._outcome_idx = OUTCOME_OPTIONS.index(
            suggested_outcome if suggested_outcome in OUTCOME_OPTIONS else "open"
        )

    def compose(self) -> ComposeResult:
        duration = _fmt_duration(self.elapsed_s)
        with Vertical(id="handover-dialog"):
            yield Label(
                f"Session abgeschlossen  ·  {self.todo_title[:40]}  ·  {duration}",
                id="handover-title",
            )

            yield Label("Ergebnis:", classes="handover-label")
            yield Label(self._outcome_str(), id="handover-rating-display")

            yield Label("Eintrag fürs Tages-Log:", classes="handover-label")
            yield Input(
                placeholder="Kurz beschreiben was passiert ist…",
                id="handover-done-input",
                classes="handover-input",
            )

            yield Label(
                "[←/→] Outcome  [Enter] Bestätigen  [Esc] Abbrechen",
                id="handover-hint",
            )

    def _outcome_str(self) -> str:
        key = OUTCOME_OPTIONS[self._outcome_idx]
        parts = []
        for i, o in enumerate(OUTCOME_OPTIONS):
            label = OUTCOME_DISPLAY[o]
            if i == self._outcome_idx:
                parts.append(f"[{label}]")
            else:
                parts.append(label)
        return "  " + "   ".join(parts)

    def _update_outcome(self) -> None:
        self.query_one("#handover-rating-display", Label).update(self._outcome_str())

    def on_key(self, event) -> None:
        if event.key == "left" and self._outcome_idx > 0:
            self._outcome_idx -= 1
            self._update_outcome()
            event.stop()
        elif event.key == "right" and self._outcome_idx < len(OUTCOME_OPTIONS) - 1:
            self._outcome_idx += 1
            self._update_outcome()
            event.stop()

    @on(Input.Submitted, "#handover-done-input")
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss({
            "outcome":    OUTCOME_OPTIONS[self._outcome_idx],
            "log_entry":  event.value.strip(),
        })

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        self.query_one("#handover-done-input", Input).focus()
