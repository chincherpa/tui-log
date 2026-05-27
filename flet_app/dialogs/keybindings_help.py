"""Modal dialog that shows all keyboard shortcuts."""

from __future__ import annotations

import flet as ft

from flet_app import theme

_BINDINGS: list[tuple[str, str]] = [
    ("L",            "Log-Eingabe fokussieren"),
    ("Space",        "Todo aktivieren / pausieren"),
    ("A",            "Neues Todo erstellen"),
    ("F",            "Fokus-Session starten / beenden"),
    ("D",            "Ausgewähltes Todo als erledigt markieren"),
    ("Shift+D",      "Log-Eintrag löschen (Bestätigung)"),
    ("X",            "Todo abbrechen (Bestätigung)"),
    ("Enter",        "Todo-Details öffnen"),
    ("E",            "Angezeigten Eintrag bearbeiten"),
    ("C",            "Tag des Eintrags ändern"),
    ("V",            "Neuesten Eintrag anzeigen"),
    ("B",            "Filter rückwärts wechseln"),
    ("N",            "Filter vorwärts wechseln"),
    ("P",            "Tag rückwärts wechseln (Eingabe)"),
    ("R",            "Alles aus DB neu laden"),
    ("M",            "Content-Panel ein-/ausblenden"),
    ("T",            "Todo-Panel ein-/ausblenden"),
    ("W",            "Wochenrückblick öffnen"),
    ("Q",            "Beenden"),
    ("↑ / K",        "Navigation nach oben"),
    ("↓ / J",        "Navigation nach unten"),
    ("Tab",          "Nächstes Panel / nächster Tag (in Eingabe)"),
    ("Shift+Tab",    "Voriges Panel / voriger Tag (in Eingabe)"),
    ("Esc",          "Dialog schließen"),
]


def show_keybindings_help(page: ft.Page) -> None:
    def _close(_e: ft.ControlEvent | None = None) -> None:
        page.pop_dialog()

    rows: list[ft.Control] = []
    for key, desc in _BINDINGS:
        rows.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(key, color=theme.ACCENT_BLUE, size=12,
                                        weight="bold", font_family="monospace"),
                        width=130,
                    ),
                    ft.Text(desc, color=theme.TEXT_PRIMARY, size=12),
                ],
                spacing=0,
            )
        )

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=theme.BG_PANEL,
        title=ft.Text("⌨  Tastenkürzel", color=theme.TEXT_PRIMARY, size=15, weight="bold"),
        content=ft.Container(
            content=ft.Column(rows, spacing=6, scroll="auto"),
            width=460,
            height=460,
        ),
        actions=[
            ft.TextButton("Schließen", on_click=_close),
        ],
        actions_alignment="end",
    )
    page.show_dialog(dlg)
