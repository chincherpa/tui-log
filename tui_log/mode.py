"""
tui_log/mode.py
~~~~~~~~~~~~~~~
Modus-Erkennung: Work | Handover (Feierabend-Ritual-Fenster)
Basiert auf Uhrzeit aus ScheduleConfig.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from enum import Enum

from .config import ScheduleConfig

class Mode(str, Enum):
    WORK     = "work"
    HANDOVER = "handover"   # Feierabend-Ritual-Fenster

def detect_mode(schedule: ScheduleConfig, now: datetime | None = None) -> Mode:
    """
    Gibt den aktuellen Modus zurück.

    Logik:
      work_start–work_end          → WORK
      work_end – work_end+handover → HANDOVER
      sonst                        → WORK
    """
    if now is None:
        now = datetime.now()

    current = now.time()
    work_end = schedule.work_end
    handover_end = _add_minutes(work_end, schedule.handover_window)

    if schedule.work_start <= current < work_end:
        return Mode.WORK
    elif work_end <= current < handover_end:
        return Mode.HANDOVER
    else:
        return Mode.WORK

def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 1, t.hour, t.minute) + timedelta(minutes=minutes)
    return dt.time()
