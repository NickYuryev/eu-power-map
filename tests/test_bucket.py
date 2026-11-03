from datetime import datetime, timedelta

from ingest.bucket import to_hourly
from ingest.labels import BRUSSELS


def _series(start: datetime, step_min: int, values: list[float | None]):
    secs = [int((start + timedelta(minutes=step_min * i)).timestamp()) for i in range(len(values))]
    return secs, values


def test_quarter_hourly_averages_to_hourly():
    start = datetime(2026, 6, 15, 0, 0, tzinfo=BRUSSELS)
    secs, vals = _series(start, 15, [100.0, 110.0, 90.0, 100.0] + [50.0] * 92)
    out = to_hourly(secs, vals)
    assert len(out) == 24
    assert out[next(iter(out))] == 100.0  # (100+110+90+100)/4


def test_null_hour_carries_forward():
    start = datetime(2026, 6, 15, 0, 0, tzinfo=BRUSSELS)
    secs, vals = _series(start, 60, [10.0, None, 20.0] + [None] * 21)
    out = to_hourly(secs, vals)
    series = list(out.values())
    assert series[0] == 10.0
    assert series[1] == 10.0  # carried forward
    assert series[2] == 20.0
    assert series[-1] == 20.0
