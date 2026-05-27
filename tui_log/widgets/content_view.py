"""
tui_log/widgets/content_view.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Widget & Modal zum Anzeigen/Bearbeiten des mehrzeiligen Log-Contents.
"""

from __future__ import annotations

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import TextArea, Label, Static
from textual.containers import Vertical

class ContentEditModal(ModalScreen[str | None]):
    """Modal zum Bearbeiten von mehrzeiligem Text. Gibt den neuen Text oder None zurück."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save")
    ]

    def __init__(self, initial_text: str = "") -> None:
        super().__init__()
        self._initial = initial_text

    def compose(self) -> ComposeResult:
        with Vertical(id="content-edit-dialog"):
            yield Label("Edit Entry", id="content-edit-title")
            yield TextArea(id="content-editor")
            yield Label("[Ctrl+S] Save    [Esc] Cancel", id="content-edit-hint")

    def on_mount(self) -> None:
        ta = self.query_one("#content-editor", TextArea)
        try:
            ta.load_text(self._initial)
        except Exception:
            # Fallback: set attribute if load_text missing
            ta.text = self._initial
        # Place cursor at end of text
        try:
            text_val = getattr(ta, "text", self._initial)
            # Use split on '\n' to preserve trailing empty line
            lines = (text_val or "").split("\n")
            last_line = max(0, len(lines) - 1)
            last_col = len(lines[-1]) if lines else 0
            # cursor_location expects a (line, column) tuple
            if hasattr(ta, "cursor_location"):
                try:
                    ta.cursor_location = (last_line, last_col)
                except Exception:
                    # best-effort: try moving to line end via action
                    try:
                        ta.action_cursor_page_down()
                        ta.action_cursor_line_end()
                    except Exception:
                        pass
        except Exception:
            pass
        ta.focus()

    def action_save(self) -> None:
        ta = self.query_one("#content-editor", TextArea)
        text = getattr(ta, "text", None)
        if text is None:
            try:
                text = ta.get_text_range(0, 10**9)
            except Exception:
                text = ""
        self.dismiss(text)

    def action_cancel(self) -> None:
        self.dismiss(None)

class ContentView(Static):
    """Einfaches read-only Widget für mehrzeiligen Content. Verwaltet set_content().

    Akzeptiert übliche Widget-KWArgs wie `id` oder `classes` und leitet sie an
    die Basisklasse weiter.
    """

    def __init__(self, content: str = "", *args, **kwargs) -> None:
        # Allow caller to override classes; otherwise provide a default
        if "classes" not in kwargs:
            kwargs["classes"] = "content-view"
        super().__init__(content, *args, **kwargs)

    def set_content(self, content: str) -> None:
        self.update(content)
