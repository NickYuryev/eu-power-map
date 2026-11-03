"""DST-correct hour labels for the Europe/Brussels wall clock.

Spring forward gives a 23-hour day; fall back gives 25. We walk UTC one hour
at a time so both cases produce the right number of local-time labels.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BRUSSELS = ZoneInfo("Europe/Brussels")
_UTC = ZoneInfo("UTC")


def hour_labels(day: date) -> list[str]:
    """ISO-8601 timestamps for every wall-clock hour of `day` in Brussels."""
    start = datetime(day.year, day.month, day.day, tzinfo=BRUSSELS)
    end_utc = (start + timedelta(days=1)).astimezone(_UTC)
    cur_utc = start.astimezone(_UTC)
    labels: list[str] = []
    while cur_utc < end_utc:
        labels.append(cur_utc.astimezone(BRUSSELS).isoformat())
        cur_utc += timedelta(hours=1)
    return labels
