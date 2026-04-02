# Todos in allen Modi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jeder Modus (Arbeit, Familie, Wochenende) bekommt eine eigene, voneinander isolierte Todo-Liste; Familie und Wochenende erhalten eine vereinfachte Variante (kein Focus-Timer, nur anlegen/abhaken/löschen).

**Architecture:** DB-Tabelle `todos` bekommt per Migration `'family'` als gültigen mode-Wert. `NewTodoModal` erhält einen `default_mode`-Parameter. Familie und Wochenende erhalten je ein Todo-Panel inline in ihren App-Klassen (kein geteiltes Widget — YAGNI). Arbeit bleibt unverändert.

**Tech Stack:** Python 3.11+, Textual ≥0.70, SQLite WAL

---

## Dateiübersicht

| Datei | Änderung |
|-------|----------|
| `tui_log/schema.py` | Migration 3: `todos`-Tabelle neu erstellen mit `'family'` im mode-Check; SCHEMA_VERSION → 3 |
| `tui_log/db_utils.py` | `TodoMode` Literal um `"family"` erweitern |
| `tui_log/widgets/new_todo.py` | `"family"` zu MODES hinzufügen; `default_mode`-Parameter |
| `tui_log/modes/family.py` | Work-Summary entfernen; horizontales Layout; Todo-Panel rechts |
| `tui_log/modes/weekend.py` | Tasten umbelegen; Todo-Panel als drittes Panel rechts |

---

## Task 1: DB-Migration — `'family'` als gültiger todos.mode

**Files:**
- Modify: `tui_log/schema.py`
- Modify: `tui_log/db_utils.py`

SQLite erlaubt kein `ALTER TABLE ... MODIFY CONSTRAINT`. Die `todos`-Tabelle muss neu erstellt werden.

- [ ] **Schritt 1: SCHEMA_VERSION in `schema.py` auf 3 setzen**

```python
# tui_log/schema.py, Zeile 16
SCHEMA_VERSION = 3
```

- [ ] **Schritt 2: Migration 3 in `_MIGRATIONS` eintragen**

In `schema.py`, nach dem schließenden `"""` von Migration 2, hinzufügen:

```python
    3: """
    -- todos.mode CHECK-Constraint um 'family' erweitern.
    -- SQLite kann Constraints nicht direkt ändern → Tabelle neu erstellen.
    PRAGMA foreign_keys=OFF;
    CREATE TABLE todos_new (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        context     TEXT,
        status      TEXT    NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','active','paused','done','dropped')),
        priority    TEXT    NOT NULL DEFAULT 'normal'
                    CHECK(priority IN ('high','normal','low')),
        mode        TEXT    NOT NULL DEFAULT 'work'
                    CHECK(mode IN ('work','family','weekend','any')),
        tags        TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        done_at     TEXT
    );
    INSERT INTO todos_new SELECT * FROM todos;
    DROP TABLE todos;
    ALTER TABLE todos_new RENAME TO todos;
    CREATE INDEX IF NOT EXISTS idx_todo_status ON todos(status);
    CREATE INDEX IF NOT EXISTS idx_todo_mode   ON todos(mode);
    PRAGMA foreign_keys=ON
    """,
```

> **Warum PRAGMA foreign_keys=OFF?** `focus_sessions` und `todo_notes` referenzieren `todos(id)` mit `ON DELETE CASCADE`. Mit FK aus wird der DROP nicht kaskadiert — die bestehenden Daten bleiben erhalten. Nach dem Rename zeigt die FK-Referenz wieder auf die richtige Tabelle.

- [ ] **Schritt 3: TodoMode in `db_utils.py` erweitern**

```python
# tui_log/db_utils.py, Zeile 27
TodoMode = Literal["work", "family", "weekend", "any"]
```

- [ ] **Schritt 4: Migration manuell testen**

```bash
python -m tui_log --mode work
# App starten → direkt beenden mit q
# Kein Fehler = Migration erfolgreich
```

Alternativ direkt prüfen:
```bash
python -c "
from pathlib import Path
from tui_log.schema import init_db, _current_version, get_connection
db = Path('journal.db')
init_db(db)
with get_connection(db, readonly=True) as c:
    print('version:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])
    # Muss 3 sein
    c.execute(\"INSERT INTO todos (title, mode) VALUES ('test', 'family')\")
print('family-mode INSERT funktioniert')
"
```

Erwartete Ausgabe: `version: 3` und `family-mode INSERT funktioniert`  
(Der INSERT schlägt fehl wenn der CHECK noch nicht aktualisiert wurde)

- [ ] **Schritt 5: Commit**

```bash
git add tui_log/schema.py tui_log/db_utils.py
git commit -m "feat: add 'family' as valid todo mode (migration 3)"
```

---

## Task 2: NewTodoModal — `default_mode`-Parameter + `'family'`-Eintrag

**Files:**
- Modify: `tui_log/widgets/new_todo.py`

- [ ] **Schritt 1: `MODES` und `MODE_DISPLAY` aktualisieren**

```python
# tui_log/widgets/new_todo.py
MODES = ["work", "family", "weekend", "any"]
MODE_DISPLAY = {
    "work":    "[#5B8DEF]work[/]",
    "family":  "[#C77DFF]family[/]",
    "weekend": "[#C8A165]weekend[/]",
    "any":     "[dim]any[/]",
}
```

- [ ] **Schritt 2: `default_mode`-Parameter zu `__init__` hinzufügen**

```python
# tui_log/widgets/new_todo.py — __init__
def __init__(self, prefill_title: str = "", default_mode: str = "work") -> None:
    super().__init__()
    self._prefill    = prefill_title
    self._prio_idx   = 1   # Default: normal
    self._mode_idx   = MODES.index(default_mode) if default_mode in MODES else 0
```

- [ ] **Schritt 3: Manuell testen**

```bash
python -m tui_log --mode work
# [a] drücken → Modal öffnen
# Mit Ctrl+← / Ctrl+→ durch die Modi radeln
# "family" muss jetzt erscheinen
```

- [ ] **Schritt 4: Commit**

```bash
git add tui_log/widgets/new_todo.py
git commit -m "feat: add family to NewTodoModal, add default_mode param"
```

---

## Task 3: Familie-Modus — Work-Summary entfernen, Todo-Panel rechts

**Files:**
- Modify: `tui_log/modes/family.py`

Das Layout wechselt von einem vertikalen Stack zu einem horizontalen Split:
```
Horizontal(id="main-split")
  Vertical(id="log-panel")   [width: 2fr]
  Vertical(id="todo-panel")  [width: 1fr]
```

- [ ] **Schritt 1: Imports erweitern**

Am Anfang von `family.py`, den bestehenden Import von `db_utils` bleibt. Sicherstellen dass `escape` importiert ist (ist bereits vorhanden).

Kein neuer Import nötig — `NewTodoModal` wird inline importiert wie `WeeklyScreen`.

- [ ] **Schritt 2: STATUS_ICONS als Modul-Konstante hinzufügen**

Nach den Helfer-Funktionen, vor `EveningModal`:

```python
# tui_log/modes/family.py — nach _evening_greeting()
_STATUS_ICONS = {
    "open":    "[dim]○[/]",
    "active":  "[bold green]▶[/]",
    "paused":  "[dim]‖[/]",
    "done":    "[dim]✓[/]",
    "dropped": "[dim]✗[/]",
}
```

- [ ] **Schritt 3: `DEFAULT_CSS` komplett ersetzen**

Den gesamten `DEFAULT_CSS`-Block in `FamilyApp` ersetzen:

```python
    DEFAULT_CSS = """
    Screen          { background: #0D0D1A; color: #C8C8C8; }
    Header          { background: #1A0D1A; color: #C77DFF; height: 1; }
    Footer          { background: #1A0D1A; color: #555577; height: 1; }

    #main-split     { layout: horizontal; height: 1fr; }

    #log-panel      { width: 2fr; border: solid #2A1A2A; padding: 0 1; }
    #log-panel:focus-within { border: solid #C77DFF; }
    #panel-title    { background: #1A0D1A; color: #C77DFF; height: 1; padding: 0 1; text-style: bold; }
    #log-list       { height: 1fr; overflow-y: auto; }

    #input-row      { height: 3; layout: horizontal; background: #1A0D1A; border-top: solid #2A1A2A; padding: 0 1; align: left middle; }
    #tag-selector   { width: auto; min-width: 12; height: 1; background: #2A1A2A; color: #C77DFF; text-style: bold; padding: 0 1; margin-right: 1; }
    #log-input      { width: 1fr; height: 1; background: #1A0D1A; color: #E8E8E8; border: none; }
    #log-input:focus{ border: none; background: #1A0D1A; }

    #todo-panel     { width: 1fr; border: solid #2A1A2A; padding: 0 1; }
    #todo-panel:focus-within { border: solid #C77DFF; }
    #todo-panel-title { background: #1A0D1A; color: #C77DFF; height: 1; padding: 0 1; text-style: bold; }
    #todo-list      { height: 1fr; overflow-y: auto; }
    """
```

- [ ] **Schritt 4: `__init__` um Todo-State erweitern**

```python
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.cfg        = config
        self.db_path    = config.db_path
        self.tags       = config.tags
        self._fam_tags  = (
            config.tags.by_category("family") + config.tags.by_category("any")
        )
        self._tag_idx   = 0
        self._entries: list[db.LogEntry] = []
        self._todos:   list[db.Todo]     = []
        self._todo_idx: int              = 0
```

- [ ] **Schritt 5: BINDINGS erweitern**

```python
    BINDINGS = [
        Binding("space,n",   "focus_input",    "Log",       show=True),
        Binding("tab",       "next_tag",       "Tag",       show=False),
        Binding("shift+tab", "prev_tag",       "Tag",       show=False),
        Binding("a",         "add_todo",       "Neu Todo",  show=True),
        Binding("up,k",      "todo_up",        "Todo ↑",    show=False),
        Binding("down,j",    "todo_down",      "Todo ↓",    show=False),
        Binding("d",         "todo_done",      "✓ Done",    show=False),
        Binding("x",         "todo_delete",    "✗ Löschen", show=False),
        Binding("e",         "evening_ritual", "Abend",     show=True),
        Binding("w",         "show_week",      "Woche",     show=True),
        Binding("r",         "refresh",        "Refresh",   show=False),
        Binding("ctrl+a",    "goto_work",      "→ Arbeit",    show=True),
        Binding("ctrl+f",    "goto_family",    "→ Familie",   show=True),
        Binding("ctrl+w",    "goto_weekend",   "→ Wochenende",show=True),
        Binding("q",         "quit",           "Beenden",   show=True),
    ]
```

- [ ] **Schritt 6: `compose()` ersetzen**

```python
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        with Horizontal(id="main-split"):
            with Vertical(id="log-panel"):
                yield Label("", id="panel-title")
                with ScrollableContainer(id="log-list"):
                    yield Static("", id="log-content")
                with Horizontal(id="input-row"):
                    yield Label("", id="tag-selector")
                    yield LogInput(placeholder="Was passiert? (Tab = Tag)", id="log-input")

            with Vertical(id="todo-panel"):
                yield Label("", id="todo-panel-title")
                with ScrollableContainer(id="todo-list"):
                    yield Static("", id="todo-list-content")

        yield Footer()
```

- [ ] **Schritt 7: `on_mount` und `_load_all` anpassen**

```python
    def on_mount(self) -> None:
        self._load_all()
        self._update_tag_selector()
        self._tick_title()

    def _load_all(self) -> None:
        self._load_family_log()
        self._load_todos()
        self._update_panel_title()
        self._update_todo_panel_title()
```

`_load_work_summary` komplett entfernen.

- [ ] **Schritt 8: Todo-Methoden hinzufügen**

Nach `_update_panel_title`:

```python
    def _load_todos(self) -> None:
        current_id = self._todos[self._todo_idx].id if self._todos else None
        self._todos = db.todo_list(self.db_path, mode="family")
        self._todos.sort(key=lambda t: (
            0 if t.status == "active"
            else 1 if t.status in ("open", "paused")
            else 2,
            t.created_at,
        ))
        if current_id is not None:
            ids = [t.id for t in self._todos]
            self._todo_idx = ids.index(current_id) if current_id in ids else 0
        self._render_todos()

    def _render_todos(self) -> None:
        if not self._todos:
            self._update("#todo-list-content", Static,
                         "[dim]  (keine Todos – [a] anlegen)[/]")
            return

        self._todo_idx = max(0, min(self._todo_idx, len(self._todos) - 1))
        lines = []
        for i, todo in enumerate(self._todos):
            selected = (i == self._todo_idx)
            icon = _STATUS_ICONS.get(todo.status, "○")
            dim  = todo.status in ("done", "dropped")
            tc   = "#444466" if dim else "#C8C8C8"
            title_s = escape(todo.title[:36])

            if selected:
                line1 = f"[bold #C77DFF]▶[/] {icon}  [bold reverse {tc}] {title_s} [/]"
                line2 = "     [dim][↑↓] Nav  [d] Done  [x] Löschen[/]"
                lines += [line1, line2, ""]
            else:
                lines += [f"  {icon}  [bold {tc}]{title_s}[/]", ""]

        self._update("#todo-list-content", Static, "\n".join(lines))

    def _update_todo_panel_title(self) -> None:
        active = sum(1 for t in self._todos if t.status in ("open", "active", "paused"))
        done   = sum(1 for t in self._todos if t.status == "done")
        self._update("#todo-panel-title", Label,
                     f"  ✅ TODOS  ·  {active} offen  ·  {done} done")
```

- [ ] **Schritt 9: Todo-Actions hinzufügen**

Nach den Tag-Selector-Methoden:

```python
    def action_todo_up(self) -> None:
        if self._todos and self._todo_idx > 0:
            self._todo_idx -= 1
            self._render_todos()

    def action_todo_down(self) -> None:
        if self._todos and self._todo_idx < len(self._todos) - 1:
            self._todo_idx += 1
            self._render_todos()

    def action_todo_done(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status == "done":
            self.notify(f"Bereits erledigt: {todo.title[:40]}", timeout=2)
            return
        db.todo_set_status(self.db_path, todo.id, "done")
        self._load_todos()
        self._update_todo_panel_title()
        self.notify(f"✓  {todo.title[:40]}", timeout=2)

    def action_todo_delete(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        db.todo_delete(self.db_path, todo.id)
        self._todo_idx = max(0, self._todo_idx - 1)
        self._load_todos()
        self._update_todo_panel_title()
        self.notify(f"✗  '{todo.title[:40]}' gelöscht", timeout=2)

    def action_add_todo(self) -> None:
        from ..widgets.new_todo import NewTodoModal

        def on_result(result: dict | None) -> None:
            if not result:
                return
            db.todo_add(
                self.db_path,
                title=result["title"],
                context=result["context"],
                priority=result["priority"],
                mode=result["mode"],
            )
            self._load_todos()
            self._update_todo_panel_title()
            self.notify(f"Todo angelegt: {result['title'][:40]}", timeout=2)

        self.push_screen(NewTodoModal(default_mode="family"), on_result)
```

- [ ] **Schritt 10: `action_refresh` anpassen**

```python
    def action_refresh(self) -> None:
        self._load_all()
```

(bleibt gleich, da `_load_all` jetzt auch Todos lädt)

- [ ] **Schritt 11: Manuell testen**

```bash
python -m tui_log --mode family
```

Prüfen:
- Layout: Log links (2/3), Todos rechts (1/3), kein Work-Summary-Block oben
- `a` → NewTodoModal, Default-Mode "family" vorausgewählt
- Todo anlegen → erscheint in der Liste
- `↑`/`↓` → Navigation
- `d` → Todo wird als done markiert
- `x` → Todo gelöscht
- `e` → Abend-Modal funktioniert noch
- `w` → Wochenrückblick funktioniert noch

- [ ] **Schritt 12: Commit**

```bash
git add tui_log/modes/family.py
git commit -m "feat: add todo panel to family mode, remove work summary"
```

---

## Task 4: Wochenende-Modus — Tasten umbelegen, Todo-Panel als drittes Panel

**Files:**
- Modify: `tui_log/modes/weekend.py`

Layout nach der Änderung:
```
Horizontal(id="main-split")
  Vertical(id="project-panel")  [width: 1fr]
  Vertical(id="log-panel")      [width: 2fr]
  Vertical(id="todo-panel")     [width: 1fr]
```

- [ ] **Schritt 1: STATUS_ICONS als Modul-Konstante hinzufügen**

Nach den `PHASE_BADGES`:

```python
# tui_log/modes/weekend.py — nach PHASE_BADGES
_STATUS_ICONS = {
    "open":    "[dim]○[/]",
    "active":  "[bold green]▶[/]",
    "paused":  "[dim]‖[/]",
    "done":    "[dim]✓[/]",
    "dropped": "[dim]✗[/]",
}
```

- [ ] **Schritt 2: BINDINGS ersetzen**

```python
    BINDINGS = [
        Binding("space,n",   "focus_input",    "Log",          show=True),
        Binding("tab",       "next_tag",       "Tag",          show=False),
        Binding("shift+tab", "prev_tag",       "Tag",          show=False),
        Binding("p",         "new_project",    "Neu Projekt",  show=True),
        Binding("shift+down","next_project",   "Projekt ▼",   show=False),
        Binding("shift+up",  "prev_project",   "Projekt ▲",   show=False),
        Binding("a",         "add_todo",       "Neu Todo",     show=True),
        Binding("up,k",      "todo_up",        "Todo ↑",       show=False),
        Binding("down,j",    "todo_down",      "Todo ↓",       show=False),
        Binding("d",         "done_project_or_todo", "✓",      show=True),
        Binding("w",         "show_week",      "Woche",        show=True),
        Binding("r",         "refresh",        "Refresh",      show=False),
        Binding("ctrl+a",    "goto_work",      "→ Arbeit",     show=True),
        Binding("ctrl+f",    "goto_family",    "→ Familie",    show=True),
        Binding("ctrl+w",    "goto_weekend",   "→ Wochenende", show=True),
        Binding("q",         "quit",           "Beenden",      show=True),
    ]
```

> **Hinweis:** `d` ist jetzt kontextsensitiv: es ruft `action_done_project_or_todo` auf, das je nach Fokus (Projekt oder Todo) die richtige Aktion ausführt. Da es kein echtes "Fokus"-Konzept zwischen den Panels gibt, nutzen wir eine einfachere Heuristik: `d` erledigt immer das aktuell ausgewählte Todo. Für "Projekt abschließen" den bestehenden Binding-Slot umnutzen oder `d` nur für Todos reservieren. Tatsächlich: `done_project` war vorher `d`. Da wir jetzt auch `d` für Todo brauchen, machen wir `d` → Todo-done, und Projekt-done bekommt kein eigenes Binding (kann über `p`-Flow erledigt werden) — oder wir nutzen `Shift+d`. Einfachste Lösung: `d` → todo_done, `shift+d` → done_project.

Binding-Korrektur:

```python
    BINDINGS = [
        Binding("space,n",   "focus_input",    "Log",           show=True),
        Binding("tab",       "next_tag",       "Tag",           show=False),
        Binding("shift+tab", "prev_tag",       "Tag",           show=False),
        Binding("p",         "new_project",    "Neu Projekt",   show=True),
        Binding("shift+down","next_project",   "Projekt ▼",    show=False),
        Binding("shift+up",  "prev_project",   "Projekt ▲",    show=False),
        Binding("a",         "add_todo",       "Neu Todo",      show=True),
        Binding("up,k",      "todo_up",        "Todo ↑",        show=False),
        Binding("down,j",    "todo_down",      "Todo ↓",        show=False),
        Binding("d",         "todo_done",      "✓ Todo",        show=False),
        Binding("shift+d",   "done_project",   "✓ Projekt",     show=True),
        Binding("x",         "todo_delete",    "✗ Löschen",     show=False),
        Binding("w",         "show_week",      "Woche",         show=True),
        Binding("r",         "refresh",        "Refresh",       show=False),
        Binding("ctrl+a",    "goto_work",      "→ Arbeit",      show=True),
        Binding("ctrl+f",    "goto_family",    "→ Familie",     show=True),
        Binding("ctrl+w",    "goto_weekend",   "→ Wochenende",  show=True),
        Binding("q",         "quit",           "Beenden",       show=True),
    ]
```

- [ ] **Schritt 3: `DEFAULT_CSS` erweitern**

Am Ende des `DEFAULT_CSS`-Blocks (vor dem schließenden `"""`), einfügen:

```css
    /* ── Todo-Panel ── */
    #todo-panel {
        width: 1fr;
        border: solid #2A2A18;
        padding: 0 1;
    }
    #todo-panel:focus-within { border: solid #C8A165; }
    #todo-panel-title {
        background: #12100A;
        color: #C8A165;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    #todo-list { height: 1fr; overflow-y: auto; }
```

- [ ] **Schritt 4: `__init__` um Todo-State erweitern**

```python
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.cfg            = config
        self.db_path        = config.db_path
        self.tags           = config.tags
        self._we_tags       = (
            config.tags.by_category("weekend") + config.tags.by_category("any")
        )
        self._tag_idx       = 0
        self._projects: list[db.Project] = []
        self._project_idx   = 0
        self._entries: list[db.LogEntry] = []
        self._todos:   list[db.Todo]     = []
        self._todo_idx: int              = 0
```

- [ ] **Schritt 5: `compose()` — Todo-Panel hinzufügen**

```python
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main-split"):
            with Vertical(id="project-panel"):
                yield Label("  🔨 PROJEKTE", id="project-title-bar")
                with ScrollableContainer(id="project-list"):
                    yield Static("", id="project-list-content")
            with Vertical(id="log-panel"):
                yield Label("", id="log-title-bar")
                with ScrollableContainer(id="log-list"):
                    yield Static("", id="log-content")
                with Horizontal(id="input-row"):
                    yield Label("", id="tag-selector")
                    yield LogInput(placeholder="Was hast du gemacht? (Tab = Tag)", id="log-input")
            with Vertical(id="todo-panel"):
                yield Label("", id="todo-panel-title")
                with ScrollableContainer(id="todo-list"):
                    yield Static("", id="todo-list-content")
        yield Footer()
```

- [ ] **Schritt 6: `_load_all` anpassen**

```python
    def _load_all(self) -> None:
        self._load_projects()
        self._load_log()
        self._load_todos()
```

- [ ] **Schritt 7: Todo-Methoden hinzufügen**

Nach `_update_log_title`:

```python
    def _load_todos(self) -> None:
        current_id = self._todos[self._todo_idx].id if self._todos else None
        self._todos = db.todo_list(self.db_path, mode="weekend")
        self._todos.sort(key=lambda t: (
            0 if t.status == "active"
            else 1 if t.status in ("open", "paused")
            else 2,
            t.created_at,
        ))
        if current_id is not None:
            ids = [t.id for t in self._todos]
            self._todo_idx = ids.index(current_id) if current_id in ids else 0
        self._render_todos()
        self._update_todo_panel_title()

    def _render_todos(self) -> None:
        if not self._todos:
            self._update("#todo-list-content", Static,
                         "[dim]  (keine Todos – [a] anlegen)[/]")
            return

        self._todo_idx = max(0, min(self._todo_idx, len(self._todos) - 1))
        lines = []
        for i, todo in enumerate(self._todos):
            selected = (i == self._todo_idx)
            icon = _STATUS_ICONS.get(todo.status, "○")
            dim  = todo.status in ("done", "dropped")
            tc   = "#444466" if dim else "#C8C8C8"
            title_s = escape(todo.title[:36])

            if selected:
                line1 = f"[bold #C8A165]▶[/] {icon}  [bold reverse {tc}] {title_s} [/]"
                line2 = "     [dim][↑↓] Nav  [d] Done  [x] Löschen[/]"
                lines += [line1, line2, ""]
            else:
                lines += [f"  {icon}  [bold {tc}]{title_s}[/]", ""]

        self._update("#todo-list-content", Static, "\n".join(lines))

    def _update_todo_panel_title(self) -> None:
        active = sum(1 for t in self._todos if t.status in ("open", "active", "paused"))
        done   = sum(1 for t in self._todos if t.status == "done")
        self._update("#todo-panel-title", Label,
                     f"  ✅ TODOS  ·  {active} offen  ·  {done} done")
```

- [ ] **Schritt 8: Todo-Actions hinzufügen**

Nach `action_done_project` (umbenannt — siehe nächster Schritt):

```python
    def action_todo_up(self) -> None:
        if self._todos and self._todo_idx > 0:
            self._todo_idx -= 1
            self._render_todos()

    def action_todo_down(self) -> None:
        if self._todos and self._todo_idx < len(self._todos) - 1:
            self._todo_idx += 1
            self._render_todos()

    def action_todo_done(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        if todo.status == "done":
            self.notify(f"Bereits erledigt: {todo.title[:40]}", timeout=2)
            return
        db.todo_set_status(self.db_path, todo.id, "done")
        self._load_todos()
        self.notify(f"✓  {todo.title[:40]}", timeout=2)

    def action_todo_delete(self) -> None:
        if not self._todos:
            return
        todo = self._todos[self._todo_idx]
        db.todo_delete(self.db_path, todo.id)
        self._todo_idx = max(0, self._todo_idx - 1)
        self._load_todos()
        self.notify(f"✗  '{todo.title[:40]}' gelöscht", timeout=2)

    def action_add_todo(self) -> None:
        from ..widgets.new_todo import NewTodoModal

        def on_result(result: dict | None) -> None:
            if not result:
                return
            db.todo_add(
                self.db_path,
                title=result["title"],
                context=result["context"],
                priority=result["priority"],
                mode=result["mode"],
            )
            self._load_todos()
            self.notify(f"Todo angelegt: {result['title'][:40]}", timeout=2)

        self.push_screen(NewTodoModal(default_mode="weekend"), on_result)
```

- [ ] **Schritt 9: `action_done_project` umbenennen und `action_new_project` binding-safe machen**

Das bisherige `action_done_project` bleibt inhaltlich gleich, ist jetzt via `shift+d` erreichbar. Keine Umbenennung nötig — der Methodenname `action_done_project` passt zum Binding `"shift+d"` nicht automatisch. In Textual matchen Bindings auf `action_`-Namen über das zweite Binding-Argument (den Action-String).

Die BINDINGS-Definition oben aus Schritt 2 ist bereits korrekt: `Binding("shift+d", "done_project", ...)` → `action_done_project()`.

`action_new_project` bleibt unverändert — das BINDING war `"a"`, ist jetzt `"p"`, aber der Methodenname bleibt `action_new_project`. Textual löst Bindings über den Action-String auf, nicht den Key.

- [ ] **Schritt 10: Projekt-Navigation Methoden umbenennen**

Die Methoden `action_next_project` und `action_prev_project` bleiben unverändert (Methodennamen passen zu `"next_project"` und `"prev_project"` in den Bindings). Keine Änderung nötig.

- [ ] **Schritt 11: `action_refresh` prüfen**

```python
    def action_refresh(self) -> None:
        self._load_all()
```

(bleibt gleich)

- [ ] **Schritt 12: Manuell testen**

```bash
python -m tui_log --mode weekend
```

Prüfen:
- Layout: Projekte links (1/3), Log Mitte (2/3), Todos rechts (1/3)
- `p` → neues Projekt anlegen
- `Shift+↓` / `Shift+↑` → zwischen Projekten wechseln
- `a` → NewTodoModal, Default-Mode "weekend"
- Todo anlegen → erscheint in der Todo-Liste
- `↑`/`↓` → Todo-Navigation
- `d` → Todo erledigt
- `Shift+d` → Projekt abschließen
- `x` → Todo löschen
- `w` → Wochenrückblick funktioniert noch

- [ ] **Schritt 13: Commit**

```bash
git add tui_log/modes/weekend.py
git commit -m "feat: add todo panel to weekend mode, rebind project keys"
```

---

## Abschluss-Check

Nach allen Tasks:
- Arbeit-Modus unverändert starten → kein Fehler
- Familie → Todo anlegen, abhaken, löschen
- Wochenende → Todo anlegen, abhaken, löschen; Projekt-Aktionen via `p` und `Shift+d`
- Familie-Todo erscheint NICHT im Wochenende und umgekehrt (`todo_list` filtert nach mode)
- "any"-Todos erscheinen in allen drei Modi (bestehende Arbeit-Todos mit mode="any" bleiben sichtbar im Arbeit-Modus)
