"""Collapse any sub-hourly Energy-Charts series into a per-hour mean.

Works for PT15M, PT30M and PT60M responses alike. Empty hours carry forward
from the previous non-null value.
"""
from __future__ import annotations

from datetime import UTC, datetime

from .labels import BRUSSELS


def to_hourly(unix_seconds: list[int], values: list[float | None]) -> dict[str, float | None]:
    """Mean of non-null values per Brussels wall-clock hour, keyed by ISO hour."""
    groups: dict[str, list[float]] = {}
    for ts, v in zip(unix_seconds, values, strict=True):
        local = datetime.fromtimestamp(ts, tz=UTC).astimezone(BRUSSELS)
        key = local.replace(minute=0, second=0, microsecond=0).isoformat()
        bucket = groups.setdefault(key, [])
        if v is not None:
            bucket.append(v)
    out: dict[str, float | None] = {}
    last: float | None = None
    for key in sorted(groups):
        vals = groups[key]
        if vals:
            last = sum(vals) / len(vals)
        out[key] = last
    return out
