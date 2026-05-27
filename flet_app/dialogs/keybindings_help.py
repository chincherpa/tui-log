"""Modal dialog that shows all keyboard shortcuts."""

from __future__ import annotations

import flet as ft

from flet_app import theme

_BINDINGS: list[tuple[str, str]] = [
    ("↑ / K",        "Navigation nach oben"),
    ("↓ / J",        "Navigation nach unten"),
    ("A",            "Neues Todo erstellen"),
    ("B",            "Filter rückwärts wechseln"),
    ("C",            "Tag des Eintrags ändern"),
    ("D",            "Ausgewähltes Todo als erledigt markieren"),
    ("E",            "Angezeigten Eintrag bearbeiten"),
    ("Enter",        "Todo-Details öffnen"),
    ("Esc",          "Dialog schließen"),
    ("F",            "Fokus-Session starten / beenden"),
    ("L",            "Log-Eingabe fokussieren"),
    ("M",            "Content-Panel ein-/ausblenden"),
    ("N",            "Filter vorwärts wechseln"),
    ("P",            "Tag rückwärts wechseln (Eingabe)"),
    ("Q",            "Beenden"),
    ("R",            "Alles aus DB neu laden"),
    ("Shift+D",      "Log-Eintrag löschen (Bestätigung)"),
    ("Shift+Tab",    "Voriges Panel / voriger Tag (in Eingabe)"),
    ("Space",        "Todo aktivieren / pausieren"),
    ("T",            "Todo-Panel ein-/ausblenden"),
    ("Tab",          "Nächstes Panel / nächster Tag (in Eingabe)"),
    ("V",            "Neuesten Eintrag anzeigen"),
    ("W",            "Wochenrückblick öffnen"),
    ("X",            "Todo abbrechen (Bestätigung)"),
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
                                        weight=ft.FontWeight.BOLD, font_family="monospace"),
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
        title=ft.Text("⌨  Tastenkürzel", color=theme.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(rows, spacing=6, scroll=ft.ScrollMode.AUTO),
            width=460,
            height=460,
        ),
        actions=[
            ft.TextButton("Schließen", on_click=_close),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)
