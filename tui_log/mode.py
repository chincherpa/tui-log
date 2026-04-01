"""
tui_log/mode.py
~~~~~~~~~~~~~~~
Modus-Erkennung: Work | Handover | Family | Weekend
Basiert ausschließlich auf Uhrzeit + Wochentag aus ScheduleConfig.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from enum import Enum

from .config import ScheduleConfig

class Mode(str, Enum):
    WORK     = "work"
    HANDOVER = "handover"   # Feierabend-Ritual-Fenster
    FAMILY   = "family"
    WEEKEND  = "weekend"

def detect_mode(schedule: ScheduleConfig, now: datetime | None = None) -> Mode:
    """
    Gibt den aktuellen Modus zurück.

    Logik:
      Wochenende (Sa/So)          → WEEKEND
      Werktag, vor work_start     → FAMILY   (früher Morgen)
      Werktag, work_start–end     → WORK
      Werktag, end – end+handover → HANDOVER
      Werktag, danach             → FAMILY
    """
    if now is None:
        now = datetime.now()

    weekday = now.weekday()   # 0=Mo … 6=So
    current = now.time()

    if weekday in schedule.weekend_days:
        return Mode.WEEKEND

    work_start = schedule.work_start
    work_end   = schedule.work_end

    # Handover-Ende
    handover_end = _add_minutes(work_end, schedule.handover_window)

    if current < work_start:
        return Mode.FAMILY
    elif current < work_end:
        return Mode.WORK
    elif current < handover_end:
        return Mode.HANDOVER
    else:
        return Mode.FAMILY

def _add_minutes(t: time, minutes: int) -> time:
    dt = datetime(2000, 1, 1, t.hour, t.minute) + timedelta(minutes=minutes)
    return dt.time()
