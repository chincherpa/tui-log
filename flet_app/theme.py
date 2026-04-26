"""Color and style constants — mirrors the dark theme of the original Textual app."""

from __future__ import annotations

# ── Background / surface ──────────────────────────────────────────────────
BG_BASE      = "#0E1117"
BG_PANEL     = "#11151C"
BG_SELECTED  = "#1E2530"
BORDER       = "#2A3340"
BORDER_ACTIVE = "#5B8DEF"

# ── Text ──────────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#E8E8E8"
TEXT_SECONDARY = "#888899"
TEXT_DIM       = "#555577"

# ── Status (todo) ─────────────────────────────────────────────────────────
STATUS_COLORS = {
    "open":      "#C8C8C8",
    "active":    "#66FF66",
    "paused":    "#FFD700",
    "done":      "#2E7D32",
    "dropped":   "#8B0000",
    "cancelled": "#8B0000",
    "focus":     "#55CCFF",
}

STATUS_ICONS = {
    "open":      "○",
    "active":    "▶",
    "paused":    "‖",
    "done":      "✓",
    "dropped":   "✗",
    "cancelled": "✗",
    "focus":     "◉",
}

# ── Priority ──────────────────────────────────────────────────────────────
PRIORITY_COLORS = {
    "high":   "#FF6B6B",
    "normal": "#C8C8C8",
    "low":    "#555577",
}

# ── Accent ────────────────────────────────────────────────────────────────
ACCENT_BLUE = "#5B8DEF"
ACCENT_RED  = "#FF6B6B"
ACCENT_GOLD = "#FFD700"
