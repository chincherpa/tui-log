"""Async git add/commit/push of journal.db with toast feedback."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

from flet_app.widgets.toast import show_toast

async def _run(*args: str, cwd: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, (out + err).decode(errors="replace")

async def _push(page: ft.Page, db_path: Path) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    cwd = str(db_path.parent)
    name = db_path.name

    show_toast(page, "git push: starting…", duration_ms=1500)

    rc, _ = await _run("git", "add", name, cwd=cwd)
    if rc != 0:
        show_toast(page, "git add fehlgeschlagen", severity="error", duration_ms=4000)
        return

    rc, out = await _run("git", "commit", "-m", f"update {timestamp}", cwd=cwd)
    if rc != 0:
        if "nothing to commit" in out:
            show_toast(page, "Keine Änderungen", duration_ms=2500)
        else:
            show_toast(page, "git commit fehlgeschlagen", severity="error", duration_ms=4000)
        return

    rc, _ = await _run("git", "push", cwd=cwd)
    if rc == 0:
        show_toast(page, f"journal.db gepushed [{timestamp}]", severity="success", duration_ms=3000)
    else:
        show_toast(page, "git push fehlgeschlagen", severity="error", duration_ms=4000)

def trigger_git_push(page: ft.Page, db_path: Path) -> None:
    """Run the async push in a background thread so the UI stays responsive."""
    def _runner() -> None:
        try:
            asyncio.run(_push(page, db_path))
        except Exception as e:
            try:
                show_toast(page, f"Push-Fehler: {e}", severity="error", duration_ms=4000)
            except Exception:
                pass

    threading.Thread(target=_runner, daemon=True).start()
