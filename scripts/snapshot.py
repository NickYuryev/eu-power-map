"""Fetch day-ahead prices for every country and write data/prices_<date>.json.

Run as `uv run scripts/snapshot.py`. Skips bidding zones that return nothing
rather than failing the whole snapshot — some zones (e.g. GB historically)
occasionally return empty payloads.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.energy_charts import BIDDING_ZONES, EnergyChartsClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def snapshot(day: date) -> dict:
    """Return one JSON-ready dict with per-country price series for `day`."""
    out: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "date": day.isoformat(),
        "unit": "EUR/MWh",
        "countries": {},
    }
    end = day + timedelta(days=1)
    skipped: list[str] = []
    with EnergyChartsClient() as api:
        for i, (country, bzn) in enumerate(BIDDING_ZONES.items()):
            if i:
                # Keep well under Energy-Charts' per-IP rate limit.
                time.sleep(3)
            try:
                series = api.fetch_price(country, day, end)
            except Exception as exc:  # one zone failing shouldn't drop the rest
                skipped.append(f"{country}({bzn}): {exc.__class__.__name__}")
                continue
            if not series.unix_seconds:
                skipped.append(f"{country}({bzn}): empty")
                continue
            out["countries"][country] = {
                "bzn": bzn,
                "unix_seconds": series.unix_seconds,
                "price": series.price,
            }
    if skipped:
        out["skipped"] = skipped
    return out


def main() -> int:
    day = date.today()
    payload = snapshot(day)
    DATA.mkdir(exist_ok=True)
    path = DATA / f"prices_{day.isoformat()}.json"
    path.write_text(json.dumps(payload, indent=2))
    kept = len(payload["countries"])
    skipped = len(payload.get("skipped", []))
    print(f"wrote {path.relative_to(ROOT)}: {kept} zones, {skipped} skipped")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
