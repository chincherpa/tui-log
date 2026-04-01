"""
tui_log/widgets/log_input.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Input-Subklasse die Tab/Shift+Tab für Tag-Wechsel reserviert,
statt den Fokus weiterzuschalten.

Sendet LogInput.TagNext / LogInput.TagPrev Messages nach oben.
"""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Input

class LogInput(Input):
    """
    Erweiterter Input-Widget für die Log-Eingabe.

    Tab        → TagNext  (Tag vorwärts)
    Shift+Tab  → TagPrev  (Tag rückwärts)
    Enter      → normales Input.Submitted
    """

    class TagNext(Message):
        """Nutzer drückte Tab im Log-Input → nächster Tag."""

    class TagPrev(Message):
        """Nutzer drückte Shift+Tab im Log-Input → vorheriger Tag."""

    def _on_key(self, event) -> None:
        if event.key == "tab":
            event.prevent_default()   # kein Focus-Cycle
            event.stop()
            self.post_message(self.TagNext())
        elif event.key == "shift+tab":
            event.prevent_default()
            event.stop()
            self.post_message(self.TagPrev())
        else:
            super()._on_key(event)
