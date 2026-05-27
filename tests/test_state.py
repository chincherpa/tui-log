"""Tests for flet_app.state.AppState — uses temp DB."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make repo importable when run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tui_log.schema import init_db
from tui_log import db_utils as db
from tui_log.tags import TagRegistry
from flet_app.state import AppState

def _make_state(tmp: Path) -> AppState:
    db_path = tmp / "journal.db"
    init_db(db_path)
    # Minimal in-memory tag registry: the production code reads from config.toml
    # but for state tests we only need keys that match what we insert.
    tags = TagRegistry.__new__(TagRegistry)
    tags._tags = {}  # not used by state
    state = AppState(db_path=db_path, tags=tags, work_tags=[])
    state.load_all()
    return state

class TestAppState(unittest.TestCase):

    def test_load_all_empty_db(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            self.assertEqual(s.log_entries, [])
            self.assertEqual(s.todos, [])
            self.assertIsNone(s.active_session)

    def test_log_entries_loaded_after_insert(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            db.log_add(s.db_path, tag_key="info", content="hello", mode="work")
            s.load_log()
            self.assertEqual(len(s.log_entries), 1)
            self.assertEqual(s.log_entries[0].content, "hello")

    def test_todo_selected_index_clamps(self):
        with tempfile.TemporaryDirectory() as td:
            s = _make_state(Path(td))
            db.todo_add(s.db_path, title="A", context=None, priority="normal", mode="work")
            db.todo_add(s.db_path, title="B", context=None, priority="normal", mode="work")
            s.load_todos()
            s.todo_idx = 99
            s.clamp_todo_idx()
            self.assertEqual(s.todo_idx, 1)

if __name__ == "__main__":
    unittest.main()
