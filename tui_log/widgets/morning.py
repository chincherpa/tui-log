"""
tui_log/widgets/morning.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Morgen-Ritual Modal – erscheint beim Start wenn kein morning_focus für heute.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static
from textual.containers import Vertical
from textual import on

class MorningModal(ModalScreen[tuple[str, int] | None]):
    """
    Gibt (focus_text, energy) zurück oder None wenn übersprungen.
    """

    BINDINGS = [
        Binding("escape", "skip", "Überspringen"),
    ]

    def __init__(self, carry_over: list[str]) -> None:
        super().__init__()
        self.carry_over = carry_over
        self._energy = 3
        self._phase = "focus"   # focus | energy | done

    def compose(self) -> ComposeResult:
        with Vertical(id="morning-dialog"):
            yield Label("☀  Guten Morgen – Tagesstart", id="morning-title")

            # Carry-over
            if self.carry_over:
                with Vertical(id="morning-carry-section"):
                    yield Label("Noch offen von gestern:", classes="dim")
                    for block in self.carry_over[:4]:
                        yield Label(f"  ↩  {block[:55]}", classes="morning-carry-item")
            else:
                yield Label("Kein Carry-over. Frischer Start! ✓", id="morning-carry-section")

            yield Label("Fokus heute:", id="morning-focus-label")
            yield Input(placeholder="Woran arbeitest du heute?", id="morning-focus-input")

            yield Label("Energie:", id="morning-energy-label")
            yield Label(self._energy_str(), id="morning-energy-display")

            yield Label("[Enter] Weiter  [Esc] Überspringen", id="morning-hint")

    def _energy_str(self) -> str:
        filled = "●" * self._energy
        empty  = "○" * (5 - self._energy)
        return f"  {filled}{empty}  {self._energy}/5   (← →  anpassen)"

    def _update_energy(self) -> None:
        self.query_one("#morning-energy-display", Label).update(self._energy_str())

    @on(Input.Submitted, "#morning-focus-input")
    def focus_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self._focus_text = text
            self._phase = "energy"
            # Fokus auf das "Fenster" selbst setzen damit Key-Events ankommen
            self.query_one("#morning-dialog").focus()

    def on_key(self, event) -> None:
        if self._phase == "energy":
            if event.key in ("left", "h") and self._energy > 1:
                self._energy -= 1
                self._update_energy()
                event.stop()
            elif event.key in ("right", "l") and self._energy < 5:
                self._energy += 1
                self._update_energy()
                event.stop()
            elif event.key in ("1", "2", "3", "4", "5"):
                self._energy = int(event.key)
                self._update_energy()
                event.stop()
            elif event.key == "enter":
                self.dismiss((self._focus_text, self._energy))
                event.stop()
            elif event.key == "escape":
                self._phase = "focus"
                self.query_one("#morning-focus-input", Input).focus()
                event.stop()

    def action_skip(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        self._focus_text = ""
        self.query_one("#morning-focus-input", Input).focus()
