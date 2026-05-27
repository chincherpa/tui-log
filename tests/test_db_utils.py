import tempfile
from pathlib import Path

from tui_log import schema
from tui_log import db_utils as db

def test_log_update():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "journal.db"
        schema.init_db(db_path)

        entry = db.log_add(db_path, tag_key="idea", content="Initial content", mode="work")
        assert entry is not None
        assert entry.content == "Initial content"

        updated = db.log_update(db_path, entry.id, content="Updated\nmultiline\ncontent")
        assert updated is not None
        assert updated.content == "Updated\nmultiline\ncontent"

        updated2 = db.log_update(db_path, entry.id, tag_key="note", resolved=1)
        assert updated2 is not None
        assert updated2.tag_key == "note"
        assert updated2.resolved == 1

if __name__ == "__main__":
    test_log_update()
    print("OK")
