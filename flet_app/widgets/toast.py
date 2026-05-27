"""Transient feedback via Flet SnackBar."""

from __future__ import annotations

import flet as ft

from flet_app import theme

def show_toast(page: ft.Page, message: str, *, severity: str = "info", duration_ms: int = 500) -> None:
    """Display a transient SnackBar at the bottom of the page."""
    bg = {
        "info":    theme.BG_PANEL,
        "warning": theme.ACCENT_GOLD,
        "error":   theme.ACCENT_RED,
        "success": theme.STATUS_COLORS["active"],
    }.get(severity, theme.BG_PANEL)
    fg = "#000000" if severity in ("warning", "success") else theme.TEXT_PRIMARY

    snack = ft.SnackBar(
        content=ft.Text(message, color=fg),
        bgcolor=bg,
        duration=duration_ms,
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()
