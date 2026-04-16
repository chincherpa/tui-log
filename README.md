# tui-log

Strukturiertes Tagesjournal fürs Terminal. Zeiterfassung, Tages-Log, Focus-Sessions und Wochenrückblick – alles tastaturgesteuert, lokal in SQLite.

---

## Inhalt

- [Konzept](#konzept)
- [Schnellstart](#schnellstart)
- [Modi](#modi)
- [Keybindings](#keybindings)
- [Todo-Verwaltung](#todo-verwaltung)
- [Tags](#tags)
- [Focus-Sessions](#focus-sessions)
- [Wochenrückblick](#wochenrückblick)
- [Konfiguration](#konfiguration)
- [Dateistruktur](#dateistruktur)
- [Datenbankschema](#datenbankschema)
- [Entwicklung](#entwicklung)

---

## Konzept

tui-log kennt deinen Tagesrhythmus und wechselt automatisch den Modus:

```
Werktag  06:00 – 15:00        →  Work-Modus
         15:00 – 15:15        →  Work-Modus  (Feierabend-Ritual aktiv)
         15:15 – Mitternacht  →  Familien-Modus
Samstag / Sonntag             →  Wochenend-Modus
```

Kein manuelles Umschalten nötig – die App startet immer im richtigen Kontext. Per Shortcut oder `--mode` lässt sich der Modus jederzeit erzwingen.

---

## Schnellstart

```bash
# Abhängigkeiten
pip install textual

# Starten (erkennt Modus automatisch)
python -m tui_log

# Modus erzwingen
python -m tui_log --mode work
python -m tui_log --mode family
python -m tui_log --mode weekend

# Alternative config.toml
python -m tui_log --config C:\pfad\config.toml

# Hilfe
python -m tui_log --help
```

Die Datenbank `journal.db` wird beim ersten Start automatisch neben der `config.toml` angelegt.

---

## Modi

### Work-Modus `06:00 – 15:00`

```
┌─ tui-log  ·  WORK  ·  Di, 31. Mär  ·  09:14  ▶ 00:23:11 ─────┐
│  📋 LOG  ·  Di, 31. Mär  ·  5 Einträge  ·  Fokus: Cache-Bug  │
│  ↩  StreamlitAPIException noch offen (gestern 14:51)           │
├────────────────────────────────┬───────────────────────────────┤
│  09:14  ✓ done    WAL gefixt  │  ✅ TODOS  ·  3 offen          │
│  10:32  💡 idea   Cache-Idee  │  ▶  ▶ get_gif debuggen         │
│  11:55  ✕ block   re-run loop │     dashboard-local  2× 1h23   │
│  13:20  ⚡ fix    _ensure_date│     [↑↓] Nav [f] Focus [d] Done│
│                                │                                │
│  [✓ done ] Eintrag…           │  ○  Robocopy-Deploy            │
│                                │  ○  Git-Auth  [block]          │
├────────────────────────────────┴───────────────────────────────┤
│  space Log  f Focus  a Neu Todo  t Todos  ^a Arbeit  q Beenden │
└────────────────────────────────────────────────────────────────┘
```

**Carry-over-Leiste** erscheint oben wenn ungelöste Blocks aus Vortagen existieren.

**Session-Bar** im Todo-Panel zeigt den laufenden Timer einer aktiven Focus-Session sekündlich (`▶ 00:23:11`). Der Timer läuft auch wenn das Focus-Modal minimiert ist.

---

### Familien-Modus `ab 15:15 an Werktagen`

```
┌─ tui-log  ·  PRIVAT  ·  Di, 31. Mär  ·  16:30 ───────────────┐
│  ── Heute bei der Arbeit ────────────────────────────────────  │
│  Fokus war: Dashboard-Performance-Bug                          │
│  09:14  ✓ done    WAL-Timeout gefixt            (gedimmt)      │
├────────────────────────────────────────────────────────────────┤
│  🏠 PRIVAT  ·  Di, 31. Mär  ·  2 Einträge                    │
│                                                                │
│  16:12  ♥ hannah   Mit Hannah gekocht, Pasta                   │
│  17:40  🐾 elliot  Elliot läuft wieder ohne Humpeln            │
│                                                                │
│  [♥ hannah] Was passiert? (Tab = Tag)                          │
├────────────────────────────────────────────────────────────────┤
│  space Log  e Abend  w Woche  ^a Arbeit  q Beenden             │
└────────────────────────────────────────────────────────────────┘
```

Reduziertes UI – kein Stress, keine Pflichtfelder. Oben eine gedimmte Arbeits-Zusammenfassung, darunter freier Familien-Log.

**Abend-Ritual** `[e]` – optionaler Tagesabschluss:
- Highlight des Tages (wird als `[high]`-Eintrag gespeichert)
- Was bleibt offen für morgen (Carry-over)
- Tagesbewertung: `~ zäh  ◎ ok  ● gut  ★ sehr gut`

---

### Wochenend-Modus `Sa / So`

```
┌─ tui-log  ·  WOCHENENDE  ·  Sa, 04. Apr ──────────────────────┐
│  🔨 PROJEKTE          │  📋 LOG  ·  Gartenhaus  ·  4 Einträge │
│                        │                                        │
│  ▶  ▶ Gartenhaus 🔨   │  09:15  🔨 bau   Schalbretter besorgt │
│     ‖ Hochbeet   🌱   │  11:30  🔨 bau   Grube ausgehoben     │
│     📐 Foto-Archiv 📷  │  13:00  ☕ pause  Mittagessen          │
│                        │  14:20  🔨 bau   Betonmix angesetzt   │
│  [a] Neu  [d] Fertig   │  [🔨 bau ] Was hast du gemacht?       │
├────────────────────────┴───────────────────────────────────────┤
│  space Log  p Projekt  a Neu  d Fertig  w Woche  q Beenden     │
└────────────────────────────────────────────────────────────────┘
```

Links: Projekt-Liste mit Phase-Badge. Rechts: Log des Tages.

Der Tag-Selector passt sich automatisch ans aktive Projekt an (Gartenhaus → `[bau]`, Hochbeet → `[gart]`).

---

## Keybindings

### Modus wechseln (überall verfügbar)

| Taste | Aktion |
|-------|--------|
| `Ctrl+A` | → Work-Modus (Arbeit) |
| `Ctrl+F` | → Familien-Modus |
| `Ctrl+W` | → Wochenend-Modus |

---

### Work-Modus

| Taste | Aktion |
|-------|--------|
| `SPACE` / `n` | Fokus auf Log-Eingabe |
| `Tab` *(im Input)* | Tag vorwärts |
| `Shift+Tab` *(im Input)* | Tag rückwärts |
| `Enter` *(im Input)* | Log-Eintrag speichern |
| `↑` / `j` | Todo nach oben |
| `↓` / `k` | Todo nach unten |
| `Enter` *(auf Todo)* | Todo aktivieren / pausieren |
| `f` | Focus-Session mit selektiertem Todo starten |
| `d` | Selektiertes Todo als done markieren |
| `x` | Selektiertes Todo löschen (mit Bestätigung) |
| `a` | Neues Todo anlegen |
| `t` | Todo-Panel ein-/ausblenden |
| `w` | Wochenrückblick öffnen |
| `r` | Alles neu laden |
| `q` | Beenden |

---

### Familien-Modus

| Taste | Aktion |
|-------|--------|
| `SPACE` / `n` | Fokus auf Log-Eingabe |
| `Tab` *(im Input)* | Tag vorwärts |
| `e` | Abend-Ritual |
| `w` | Wochenrückblick |
| `q` | Beenden |

---

### Wochenend-Modus

| Taste | Aktion |
|-------|--------|
| `SPACE` / `n` | Fokus auf Log-Eingabe |
| `Tab` *(im Input)* | Tag vorwärts |
| `p` / `Shift+P` | Projekt vor / zurück |
| `a` | Neues Projekt anlegen |
| `d` | Aktives Projekt als fertig markieren |
| `w` | Wochenrückblick |
| `q` | Beenden |

---

### Focus-Session

| Taste | Aktion |
|-------|--------|
| `Tab` | Timer-Preset wechseln (25 · 45 · 90 · Offen) |
| `Enter` *(im Notiz-Input)* | Notiz einwerfen |
| `1` / `2` / `3` | Outcome vorwählen (Gelöst / Offen / Blockiert) |
| `Ctrl+S` | Session beenden → Debriefing |
| `Esc` | Minimieren (Session + Timer laufen weiter) |

---

### Wochenrückblick

| Taste | Aktion |
|-------|--------|
| `←` / `h` | Vorwoche |
| `→` / `l` | Nächste Woche |
| `Esc` / `q` / `Enter` | Zurück |

---

## Todo-Verwaltung

### Anlegen `[a]`

Das Neu-Todo-Modal öffnet sich. Wenn bereits Text im Log-Input steht, wird er als Titel vorausgefüllt.

```
○  Neues Todo
──────────────────────────────────────────────────────
Titel:    [ exam time logging deinit               ]
Kontext:  [ EXAM                      (optional)   ]
Priorität:  (← →)   ▲ high   [● normal]   ▼ low
Modus:    (Ctrl+← →)  [work]   weekend   any

[Enter] Speichern  [Tab] Nächstes Feld  [Esc] Abbrechen
```

### Navigation `↑` `↓` / `j` `k`

Das selektierte Todo wird mit `▶` markiert und zeigt Aktions-Hints:

```
▶ ○  exam time logging deinit
     EXAM  [↑↓] Nav  [f] Focus  [Enter] Aktiv  [d] Done  [x] Löschen
```

### Aktivieren `[Enter]`

Setzt Status ohne Timer: `open` / `paused` → `active`, `active` → `paused`.

### Focus starten `[f]`

Startet eine Focus-Session auf dem selektierten Todo. Ist das selektierte Todo done/dropped, wird automatisch das erste offene genommen.

### Als done markieren `[d]`

Setzt Status auf `done` und schreibt automatisch einen `[done]`-Eintrag mit dem Todo-Titel ins Tages-Log.

### Löschen `[x]`

Öffnet Bestätigungs-Dialog:

```
┌──────────────────────────────────────────────────────┐
│  'exam time logging deinit' wirklich löschen?        │
│                                                      │
│  [y / Enter] Ja    [n / Esc] Nein                    │
└──────────────────────────────────────────────────────┘
```

Löscht das Todo inkl. aller verknüpften Sessions und Notizen (CASCADE).

### Laufender Timer

Eine aktive Focus-Session zeigt den Timer sekündlich in der Session-Bar oben im Todo-Panel:

```
  ▶  exam time logging deinit  ·  00:23:11
```

Der Timer läuft auch wenn das Focus-Modal per `[Esc]` minimiert wurde.

---

## Tags

Tags werden in `config.toml` definiert. Jeder Tag hat Symbol, Name, Farbe und Kategorie.

### Work-Tags

| Tag | Symbol | Farbe | Bedeutung |
|-----|--------|-------|-----------|
| `done` | ✓ | `#00C896` | Aufgabe erledigt |
| `start` | ▶ | `#5B8DEF` | Beginn einer Aktivität |
| `block` | ✕ | `#FF6B6B` | Blocker / Problem |
| `idea` | 💡 | `#C77DFF` | Idee / Erkenntnis |
| `fix` | ⚡ | `#FFD93D` | Bugfix |
| `deploy` | ⬆ | `#4FC3F7` | Deployment |
| `meet` | ● | `#FF9A3C` | Meeting |

### Familien-Tags

| Tag | Symbol | Farbe |
|-----|--------|-------|
| `hannah` | ♥ | `#FF85A1` |
| `elliot` | 🐾 | `#A0C4FF` |
| `high` | ★ | `#FFD93D` |
| `schwer` | ~ | `#FF6B6B` |

### Wochenend-Tags

| Tag | Symbol | Farbe |
|-----|--------|-------|
| `bau` | 🔨 | `#C8A165` |
| `gart` | 🌱 | `#7BC67E` |
| `foto` | 📷 | `#B0BEC5` |
| `pause` | ☕ | `#A0A0A0` |

### Universell

| Tag | Symbol | Bedeutung |
|-----|--------|-----------|
| `note` | · | Freie Notiz (in allen Modi verfügbar) |

---

## Focus-Sessions

Eine Focus-Session verbindet ein Todo mit Zeiterfassung und Live-Notizen.

### Ablauf

```
Todo auswählen  →  [f] drücken  →  Focus-Modal
                                        │
                              Timer läuft (25 / 45 / 90 / Offen)
                              Notizen per Enter einwerfen
                              Outcome mit 1/2/3 vorwählen
                                        │
                        [Esc] Minimieren       [Ctrl+S] Beenden
                              │                      │
                        Timer läuft          Debriefing-Modal
                        im Hintergrund       Outcome + Log-Eintrag
                        Session-Bar          ↓
                        tickt sekündlich     Automatisch ins Tages-Log
```

### Timer-Presets

| Preset | Dauer | Wann |
|--------|-------|------|
| 25 min | Pomodoro | Kurze, klar abgegrenzte Tasks |
| 45 min | Deep Work | Technische Analyse, Code-Reviews |
| 90 min | Großblock | Komplexe Implementierungen |
| Offen | Unbegrenzt | Wenn unklar wie lang es dauert |

### Kontext-Panel

Das Focus-Modal zeigt automatisch relevante Log-Einträge der letzten Wochen zum selben Todo (Keyword-Matching auf Titel). So siehst du sofort wo du aufgehört hast.

### Session-Ende

Nach `[Ctrl+S]` öffnet das Debriefing:
- **Outcome wählen** (← →): Gelöst · Weiter offen · Blockiert
- **Log-Eintrag** formulieren – wird automatisch als `[done]` oder `[block]` ins Tages-Log geschrieben
- **Notizen** aus der Session werden in `todo_notes` gespeichert
- **Todo-Status** wird automatisch gesetzt: Gelöst → `done`, sonst → `paused`

### Minimieren

`[Esc]` im Focus-Modal minimiert die Session – Timer und Session-Bar laufen weiter. Erneutes `[f]` bringt das Modal zurück.

---

## Wochenrückblick

Aufruf aus jedem Modus mit `[w]`. Zeigt eine vollständige Wochenauswertung:

```
KW 14  ·  28. Mär – 03. Apr 2026  (diese Woche)
────────────────────────────────────────────────────────────

ARBEIT
  Arbeitstage: 5     Energie: ●●●○○  3.2/5
  ✓ 12 done  ⚡ 3 fix  💡 4 ideas  ✕ 2 blocks
  Top: done 12×  idea 4×  fix 3×  block 2×
  Focus-Zeit: 4h 23m

WOCHENENDE
  Projekte: Gartenhaus  ·  Hochbeet

TAGESBEWERTUNGEN
  Mo ●   Di ●   Mi ~   Do ●   Fr ★   Sa ·   So ·

HIGHLIGHTS
  ★  Di  Elliot läuft wieder ohne Humpeln
  ★  Do  Pasta mit Hannah, langer Abend

FOKUS DER WOCHE
  Mo  Dashboard-Performance-Bug
  Di  Cache-Strategie testen
  Mi  Robocopy-Deploy abschließen
```

Navigation mit `←` / `→` durch vergangene Wochen. Vorwärts über die aktuelle Woche hinaus ist gesperrt.

---

## Konfiguration

Die `config.toml` liegt im Projektverzeichnis (Entwicklung) oder unter `~/.config/tui-log/config.toml`.

### Arbeitszeiten

```toml
[schedule]
work_start      = "06:00"
work_end        = "15:00"
handover_window = 15       # Minuten nach work_end: noch Work-Modus
weekend_days    = [5, 6]   # 0=Mo … 6=So
```

### Projekte

```toml
[projects]
active = ["Gartenhaus", "Hochbeet", "Foto-Archiv"]
```

Projekte werden beim Start automatisch in die DB synchronisiert. Bereits angelegte Projekte bleiben unverändert.

### Tags anpassen

```toml
[tags.work]
done   = { symbol = "✓",  name = "Erledigt",   color = "#00C896", active = true }
block  = { symbol = "✕",  name = "Blockiert",  color = "#FF6B6B", active = true }
idea   = { symbol = "💡", name = "Idee",       color = "#C77DFF", active = true }
# ...

[tags.family]
hannah = { symbol = "♥",  name = "Hannah",     color = "#FF85A1", active = true }
# ...

[tags.weekend]
bau    = { symbol = "🔨", name = "Bauen",      color = "#C8A165", active = true }
# ...

[tags.any]
note   = { symbol = "·",  name = "Notiz",      color = "#D0D0D0", active = true }
```

Felder pro Tag:
- `symbol` – Unicode-Zeichen (Emoji möglich)
- `name` – Anzeigename (momentan intern)
- `color` – Hex-Farbe `#RRGGBB`
- `active` – `false` blendet den Tag aus

---

## Dateistruktur

```
tui-log/
├── config.toml                   ← Konfiguration
├── journal.db                    ← SQLite-Datenbank (auto-generiert)
├── requirements.txt
│
└── tui_log/
    ├── __init__.py
    ├── __main__.py               ← Einstiegspunkt + Modus-Router + argparse
    │
    ├── config.py                 ← Config-Loader (AppConfig)
    ├── tags.py                   ← Tag-Dataclass + TagRegistry
    ├── mode.py                   ← Modus-Erkennung (Zeit + Wochentag)
    ├── schema.py                 ← SQLite-Schema + Migrationen
    ├── db_utils.py               ← CRUD-Funktionen für alle Tabellen
    │
    ├── work_app.py               ← Work-Modus Textual-App
    ├── work.tcss                 ← CSS für Work-Modus
    │
    ├── modes/
    │   ├── family.py             ← Familien-Modus App
    │   └── weekend.py            ← Wochenend-Modus App
    │
    ├── views/
    │   └── weekly.py             ← Wochenrückblick (Screen)
    │
    └── widgets/
        ├── log_input.py          ← Input-Subklasse (Tab = Tag, kein Focus-Cycle)
        ├── focus.py              ← Focus-Session Modal
        ├── debriefing.py         ← Session-Debriefing Modal
        └── new_todo.py           ← Neues-Todo Modal
```

---

## Datenbankschema

Alle Daten liegen in einer lokalen SQLite-Datei (`journal.db`). WAL-Mode aktiviert.

### Tabellen

**`log_entries`** – Ein Eintrag pro geloggter Aktivität

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | INTEGER PK | |
| `date` | TEXT | ISO-Datum `2026-03-31` |
| `created_at` | TEXT | Timestamp (localtime) |
| `tag_key` | TEXT | z.B. `done`, `block` |
| `mode` | TEXT | `work` / `family` / `weekend` |
| `content` | TEXT | Freitext |
| `todo_id` | INTEGER | FK → todos (optional) |

**`day_meta`** – Tages-Metadaten pro Tag

| Feld | Beschreibung |
|------|--------------|
| `date` PK | ISO-Datum |
| `morning_focus` | Optionaler Tagesfokus (Bestandsdaten) |
| `morning_energy` | Optionaler Energie-Wert 1–5 (Bestandsdaten) |
| `evening_done` | Was erledigt wurde |
| `evening_open` | Carry-over für morgen |
| `day_rating` | `zaeh` / `ok` / `gut` / `sehr_gut` |
| `work_locked` | 1 nach Feierabend-Ritual |

**`todos`** – Aufgaben

| Feld | Beschreibung |
|------|--------------|
| `id` PK | |
| `title` | Titel |
| `context` | z.B. `dashboard-local` |
| `status` | `open` / `active` / `paused` / `done` / `dropped` |
| `priority` | `high` / `normal` / `low` |
| `mode` | `work` / `weekend` / `any` |
| `tags` | JSON-Array `["work", "idea"]` |

**`focus_sessions`** – Zeitblöcke auf Todos

| Feld | Beschreibung |
|------|--------------|
| `todo_id` FK | |
| `started_at` | Timestamp |
| `ended_at` | Timestamp (NULL während laufend) |
| `duration_s` | Dauer in Sekunden |
| `timer_preset` | `"25"` / `"45"` / `"90"` / `"open"` |
| `outcome` | `solved` / `open` / `blocked` |
| `log_entry` | Auto-Text fürs Tages-Log |

**`todo_notes`** – Freie Notizen während einer Focus-Session (verknüpft mit Todo + Session)

**`projects`** – Wochenend-Projekte mit Phasen (`planning → active → paused → done`)

**`schema_version`** – Migrations-Tracker

### Migrationen

Neue Felder oder Tabellen als nummerierte Migration in `schema.py` ergänzen:

```python
_MIGRATIONS: dict[int, str] = {
    1: "... bestehendes Schema ...",
    2: "ALTER TABLE todos ADD COLUMN archived INTEGER DEFAULT 0;",
}
```

`migrate()` ist idempotent – bereits angewendete Versionen werden übersprungen.

---

## Entwicklung

### Abhängigkeiten

```
textual >= 0.70.0
```

Keine weiteren externen Abhängigkeiten. SQLite und tomllib sind in der Python-Stdlib (ab 3.11).

### Tests ausführen

```bash
python tests/test_db_utils.py
```

Eigenständiger Test-Runner (kein pytest nötig), nutzt temporäre In-Memory-DB.

### Neuen Tag hinzufügen

1. `config.toml` ergänzen:
   ```toml
   [tags.work]
   review = { symbol = "👁", name = "Review", color = "#88BBFF", active = true }
   ```
2. App neu starten – der Tag ist sofort verfügbar.

### Neuen Modus hinzufügen

1. App-Klasse in `modes/` anlegen (analog `family.py`)
2. Modus-Bedingung in `mode.py` erweitern
3. Import + Routing in `__main__.py` verdrahten

### Neue Migration schreiben

```python
# schema.py
_MIGRATIONS[2] = """
    ALTER TABLE todos ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX IF NOT EXISTS idx_todo_archived ON todos(archived);
"""
SCHEMA_VERSION = 2
```

Wird beim nächsten Start automatisch angewendet.

### Abstürze debuggen

Textual schreibt den vollständigen Traceback ins Log:

```
Windows:  %APPDATA%\textual.log
Linux/Mac: ~/.textual.log
```

---

*tui-log – gebaut für einen 06:00–15:00 Werktag, Feierabend mit Familie, und Wochenenden auf der Baustelle.*
