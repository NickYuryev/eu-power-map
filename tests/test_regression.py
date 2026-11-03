"""Regression tests pinned to known-tricky real-world days.

- 15-minute resolution (Energy-Charts switched much of EU to PT15M in 2025).
- DST spring-forward: Europe/Brussels gets a 23-hour day on the last Sunday
  of March; the "02:00" hour never exists in local time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ingest.bucket import to_hourly
from ingest.labels import BRUSSELS, hour_labels


UTC = ZoneInfo("UTC")


def test_pt15m_day_collapses_to_24_hours():
    """A PT15M response (96 points) must bucket to 24 hourly means."""
    day = date(2026, 4, 15)  # not DST transition
    start = datetime(day.year, day.month, day.day, tzinfo=BRUSSELS).astimezone(UTC)
    secs: list[int] = []
    vals: list[float | None] = []
    for i in range(96):  # 4 per hour, 24 hours
        secs.append(int((start + timedelta(minutes=15 * i)).timestamp()))
        # per-hour value is (i // 4) * 10 across every quarter, so hourly mean = 10*h
        vals.append((i // 4) * 10.0)

    hourly = to_hourly(secs, vals)
    assert len(hourly) == 24
    for h, key in enumerate(hour_labels(day)):
        assert hourly[key] == 10.0 * h


def test_dst_spring_forward_is_23_hours():
    """Brussels loses one hour on the last Sunday of March."""
    day = date(2026, 3, 29)  # EU DST starts 29 March 2026
    labels = hour_labels(day)
    assert len(labels) == 23
    # The missing hour is 02:00 local; it must not appear in the labels.
    assert not any(label.startswith(f"{day.isoformat()}T02") for label in labels)
    # 01:00 and 03:00 both present (03:00 is the first CEST hour).
    assert any(label.startswith(f"{day.isoformat()}T01") for label in labels)
    assert any(label.startswith(f"{day.isoformat()}T03") for label in labels)


def test_dst_spring_forward_buckets_correctly():
    """Hourly resolution across the DST jump: 23 hours of values, no gap."""
    day = date(2026, 3, 29)
    start = datetime(day.year, day.month, day.day, tzinfo=BRUSSELS).astimezone(UTC)
    secs = [int((start + timedelta(hours=h)).timestamp()) for h in range(23)]
    vals = [float(h) for h in range(23)]
    hourly = to_hourly(secs, vals)
    labels = hour_labels(day)
    assert len(hourly) == 23
    for h, key in enumerate(labels):
        assert hourly[key] == float(h)
