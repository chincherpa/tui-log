"""
tui_log/config.py
~~~~~~~~~~~~~~~~~
Zentraler Config-Loader.
Liest config.toml einmalig und stellt alles als typisiertes Objekt bereit.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from .tags import TagRegistry

@dataclass
class ScheduleConfig:
    work_start: time
    work_end: time
    handover_window: int          # Minuten
    weekend_days: list[int]       # 0=Mo … 6=So

    @classmethod
    def from_dict(cls, d: dict) -> "ScheduleConfig":
        def _parse_time(s: str) -> time:
            h, m = map(int, s.split(":"))
            return time(h, m)
        return cls(
            work_start=_parse_time(d["work_start"]),
            work_end=_parse_time(d["work_end"]),
            handover_window=int(d.get("handover_window", 15)),
            weekend_days=list(d.get("weekend_days", [5, 6])),
        )

@dataclass
class AppConfig:
    schedule: ScheduleConfig
    projects: list[str]
    tags: TagRegistry

    # ── Pfade ────────────────────────────────────────────────────────────────
    config_path: Path = field(repr=False)
    db_path: Path     = field(repr=False)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        """
        Lädt config.toml (Standard: neben der Datei im Projektroot).
        DB liegt immer neben der config.toml als journal.db.
        """
        if config_path is None:
            config_path = _default_config_path()

        if not config_path.exists():
            raise FileNotFoundError(
                f"config.toml nicht gefunden: {config_path}\n"
                f"Hinweis: Standardpfad ist ~/.config/tui-log/config.toml"
            )

        with open(config_path, "rb") as f:
            raw = tomllib.load(f)

        schedule = ScheduleConfig.from_dict(raw.get("schedule", {}))
        projects = raw.get("projects", {}).get("active", [])
        tags = TagRegistry.from_config(config_path)
        db_path = config_path.parent / "journal.db"

        return cls(
            schedule=schedule,
            projects=projects,
            tags=tags,
            config_path=config_path,
            db_path=db_path,
        )

    def summary(self) -> str:
        s = self.schedule
        lines = [
            "── AppConfig ───────────────────────────────",
            f"  Config:    {self.config_path}",
            f"  DB:        {self.db_path}",
            f"  Arbeitszeit: {s.work_start.strftime('%H:%M')} – {s.work_end.strftime('%H:%M')}",
            f"  Handover:  {s.handover_window} min",
            f"  Wochenende: Tage {s.weekend_days}",
            f"  Projekte:  {', '.join(self.projects) or '–'}",
            "",
            self.tags.summary(),
        ]
        return "\n".join(lines)

def _default_config_path() -> Path:
    """
    Suchpfade in Priorität:
    1. Neben dem Skript (Entwicklungsmodus)
    2. ~/.config/tui-log/config.toml
    """
    local = Path(__file__).parent.parent / "config.toml"
    if local.exists():
        return local
    return Path.home() / ".config" / "tui-log" / "config.toml"
