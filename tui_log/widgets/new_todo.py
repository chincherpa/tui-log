"""
tui_log/widgets/new_todo.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modal zum Anlegen eines neuen Todos.

Felder:
  - Titel        (Pflicht)
  - Kontext      (optional, z.B. "dashboard-local")
  - Priorität    (← → : high / normal / low)

Enter im letzten Feld → speichern.
Esc → abbrechen.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical
from textual import on

PRIORITIES = ["high", "normal", "low"]
PRIORITY_DISPLAY = {
    "high":   "[bold #FF6B6B]▲ high[/]",
    "normal": "[#C8C8C8]● normal[/]",
    "low":    "[dim]▼ low[/]",
}

class NewTodoModal(ModalScreen[dict | None]):
    """
    Rückgabe: {title, context, priority, mode} oder None bei Abbruch.
    """

    BINDINGS = [Binding("escape", "cancel", "Abbrechen")]

    DEFAULT_CSS = """
    NewTodoModal { align: center middle; }

    #todo-dialog {
        background: #0A0A1A;
        border: solid #5B8DEF;
        width: 58;
        height: auto;
        padding: 1 2;
    }
    #todo-dialog-title {
        color: #5B8DEF;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }
    .todo-field-label {
        color: #888899;
        text-style: bold;
        height: 1;
    }
    .todo-input {
        background: #12122A;
        color: #E8E8E8;
        border: solid #2A2A44;
        margin-bottom: 1;
    }
    .todo-input:focus {
        border: solid #5B8DEF;
    }
    #todo-priority-display {
        height: 1;
        margin-bottom: 1;
    }
    #todo-hint {
        color: #444466;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, prefill_title: str = "") -> None:
        super().__init__()
        self._prefill    = prefill_title
        self._prio_idx   = 1   # Default: normal

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="todo-dialog"):
            yield Label("○  Neues Todo", id="todo-dialog-title")

            yield Label("Titel:", classes="todo-field-label")
            yield Input(
                value=self._prefill,
                placeholder="Was muss erledigt werden?",
                id="todo-title-input",
                classes="todo-input",
            )

            yield Label("Kontext:", classes="todo-field-label")
            yield Input(
                placeholder="z.B. dashboard-local  (optional)",
                id="todo-context-input",
                classes="todo-input",
            )

            yield Label("Priorität:  [dim](← →)[/]", classes="todo-field-label")
            yield Label(self._prio_str(), id="todo-priority-display")

            yield Label(
                "[Enter] Speichern  [Tab] Nächstes Feld  [Esc] Abbrechen",
                id="todo-hint",
            )

    # ── Anzeige ──────────────────────────────────────────────────────────────

    def _prio_str(self) -> str:
        parts = []
        for i, p in enumerate(PRIORITIES):
            label = PRIORITY_DISPLAY[p]
            parts.append(f"[reverse]{label}[/]" if i == self._prio_idx else label)
        return "  " + "   ".join(parts)

    def _refresh_prio(self) -> None:
        self.query_one("#todo-priority-display", Label).update(self._prio_str())

    # ── Keys ─────────────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        focused = self.focused
        if focused is None:
            return

        # Prio/Mode mit ← → steuern – egal welches Feld fokussiert ist
        if event.key == "left":
            if self._prio_idx > 0:
                self._prio_idx -= 1
                self._refresh_prio()
                event.stop()
        elif event.key == "right":
            if self._prio_idx < len(PRIORITIES) - 1:
                self._prio_idx += 1
                self._refresh_prio()
                event.stop()

    # ── Eingabe ──────────────────────────────────────────────────────────────

    @on(Input.Submitted, "#todo-title-input")
    def title_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.query_one("#todo-context-input", Input).focus()

    @on(Input.Submitted, "#todo-context-input")
    def context_submitted(self, _) -> None:
        self._save()

    def _save(self) -> None:
        title = self.query_one("#todo-title-input", Input).value.strip()
        if not title:
            self.query_one("#todo-title-input", Input).focus()
            return
        context = self.query_one("#todo-context-input", Input).value.strip() or None
        self.dismiss({
            "title":    title,
            "context":  context,
            "priority": PRIORITIES[self._prio_idx],
            "mode":     "work",
        })

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        self.query_one("#todo-title-input", Input).focus()
