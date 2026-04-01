"""
tui_log/tags.py
~~~~~~~~~~~~~~~
Tag-Definitionen laden, validieren und bereitstellen.
Quelle: config.toml  →  dict[str, Tag]
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Erlaubte Kategorien – bestimmt in welchem Modus ein Tag auftaucht
CATEGORIES = ("work", "family", "weekend", "any")

@dataclass(frozen=True)
class Tag:
    key: str
    symbol: str
    name: str
    color: str        # Hex: "#RRGGBB"
    category: str     # work | family | weekend | any
    active: bool = True

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"Ungültige Kategorie '{self.category}' für Tag '{self.key}'")
        if not self.color.startswith("#") or len(self.color) != 7:
            raise ValueError(f"Ungültige Farbe '{self.color}' für Tag '{self.key}' (erwartet #RRGGBB)")

    # ── Darstellung ──────────────────────────────────────────────────────────

    def label(self) -> str:
        """Kurzes Label für den Log: '✓ done'"""
        return f"{self.symbol} {self.key}"

    def rich_label(self) -> str:
        """Rich-Markup für Textual/Rich: farbiges Label."""
        return f"[{self.color}]{self.symbol} {self.key}[/]"

    def rgb(self) -> tuple[int, int, int]:
        """Hex-Farbe als (r, g, b)-Tuple."""
        h = self.color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def __str__(self) -> str:
        return f"[{self.key}]"

# ── TagRegistry ──────────────────────────────────────────────────────────────

class TagRegistry:
    """
    Zentrales Verzeichnis aller Tags.
    Wird einmalig beim Start geladen und dann überall genutzt.

    Beispiel:
        registry = TagRegistry.from_config(Path("config.toml"))
        tag = registry["done"]           # Tag-Objekt
        work_tags = registry.by_category("work")
    """

    def __init__(self, tags: dict[str, Tag]) -> None:
        self._tags: dict[str, Tag] = tags

    # ── Laden ────────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: Path) -> "TagRegistry":
        """Liest [tags.*] aus config.toml und gibt eine TagRegistry zurück."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config nicht gefunden: {config_path}")

        with open(config_path, "rb") as f:
            raw = tomllib.load(f)

        tags_raw = raw.get("tags", {})
        if not tags_raw:
            raise ValueError("config.toml enthält keinen [tags]-Block")

        tags: dict[str, Tag] = {}
        errors: list[str] = []

        for category, entries in tags_raw.items():
            if category not in CATEGORIES:
                errors.append(f"Unbekannte Tag-Kategorie: '{category}'")
                continue
            for key, meta in entries.items():
                if key in tags:
                    errors.append(f"Doppelter Tag-Key: '{key}'")
                    continue
                try:
                    tags[key] = Tag(key=key, category=category, **meta)
                except (TypeError, ValueError) as e:
                    errors.append(f"Tag '{key}': {e}")

        if errors:
            raise ValueError("Fehler beim Laden der Tags:\n" + "\n".join(f"  · {e}" for e in errors))

        return cls(tags)

    # ── Zugriff ──────────────────────────────────────────────────────────────

    def __getitem__(self, key: str) -> Tag:
        try:
            return self._tags[key]
        except KeyError:
            raise KeyError(f"Unbekannter Tag: '[{key}]'")

    def __contains__(self, key: str) -> bool:
        return key in self._tags

    def __iter__(self) -> Iterator[Tag]:
        return iter(self._tags.values())

    def __len__(self) -> int:
        return len(self._tags)

    def get(self, key: str, default: Tag | None = None) -> Tag | None:
        return self._tags.get(key, default)

    def by_category(self, category: str) -> list[Tag]:
        """Alle aktiven Tags einer Kategorie."""
        return [t for t in self._tags.values() if t.category == category and t.active]

    def active_keys(self) -> set[str]:
        return {k for k, t in self._tags.items() if t.active}

    def all_categories(self) -> list[str]:
        seen = []
        for t in self._tags.values():
            if t.category not in seen:
                seen.append(t.category)
        return seen

    def summary(self) -> str:
        """Kurze Übersicht für Debug/Start."""
        lines = [f"TagRegistry · {len(self._tags)} Tags geladen"]
        for cat in CATEGORIES:
            tags = self.by_category(cat)
            if tags:
                keys = "  ".join(t.key for t in tags)
                lines.append(f"  [{cat:8s}]  {keys}")
        return "\n".join(lines)
