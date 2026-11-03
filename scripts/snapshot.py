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

from ingest.bucket import to_hourly  # noqa: E402
from ingest.energy_charts import BIDDING_ZONES, EnergyChartsClient  # noqa: E402
from ingest.flows import build_pairs  # noqa: E402
from ingest.labels import hour_labels  # noqa: E402
from ingest.spark import compute_clean_dark  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def snapshot(day: date) -> dict:
    """Return one JSON-ready dict with per-country hourly prices for `day`."""
    labels = hour_labels(day)
    out: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "date": day.isoformat(),
        "unit": "EUR/MWh",
        "hours": labels,
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
            hourly = to_hourly(series.unix_seconds, series.price)
            # Align to label order so DST 23/25-hour days line up.
            prices = [hourly.get(h) for h in labels]
            out["countries"][country] = {"bzn": bzn, "prices": prices}
    if skipped:
        out["skipped"] = skipped
    return out


def flows_snapshot(day: date) -> dict:
    """Hourly cross-border flows for `day`, in MW with first-ISO-positive sign."""
    labels = hour_labels(day)
    out: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "date": day.isoformat(),
        "unit": "MW",
        "hours": labels,
        "pairs": {},
    }
    end = day + timedelta(days=1)
    responses = {}
    skipped: list[str] = []
    with EnergyChartsClient() as api:
        for i, country in enumerate(BIDDING_ZONES):
            if i:
                time.sleep(3)
            try:
                responses[country] = api.fetch_cbpf(country, day, end)
            except Exception as exc:
                skipped.append(f"{country}: {exc.__class__.__name__}")
    out["pairs"] = build_pairs(responses, labels)
    if skipped:
        out["skipped"] = skipped
    return out


def spark_snapshot(prices: dict) -> dict:
    """Apply clean-dark spark formula to a prices snapshot."""
    ttf = json.loads((DATA / "ttf.json").read_text())
    eua = json.loads((DATA / "eua.json").read_text())
    out: dict[str, object] = {
        "generated_at": prices["generated_at"],
        "date": prices["date"],
        "unit": "EUR/MWh gross margin",
        "formula": "price - 0.49*TTF - 0.37*EUA",
        "ttf_eur_per_mwh": ttf["close_eur_per_mwh"],
        "ttf_date": ttf["date"],
        "eua_eur_per_tco2": eua["price_eur_per_tco2"],
        "eua_date": eua["source_date"],
        "hours": prices["hours"],
        "countries": {},
    }
    for code, c in prices["countries"].items():
        out["countries"][code] = {
            "bzn": c["bzn"],
            "spread": compute_clean_dark(
                c["prices"], ttf["close_eur_per_mwh"], eua["price_eur_per_tco2"]
            ),
        }
    return out


def _write(path: Path, payload: dict) -> None:
    body = json.dumps(payload, indent=2)
    path.write_text(body)
    (path.parent / f"{path.stem.split('_')[0]}_latest.json").write_text(body)


def main() -> int:
    day = date.today()
    DATA.mkdir(exist_ok=True)
    prices = snapshot(day)
    _write(DATA / f"prices_{day.isoformat()}.json", prices)
    kept = len(prices["countries"])
    print(f"prices: {kept}/{len(BIDDING_ZONES)} zones, "
          f"{len(prices.get('skipped', []))} skipped")
    flows = flows_snapshot(day)
    _write(DATA / f"flows_{day.isoformat()}.json", flows)
    print(f"flows: {len(flows['pairs'])} pairs, "
          f"{len(flows.get('skipped', []))} source countries skipped")
    spark = spark_snapshot(prices)
    _write(DATA / f"spark_{day.isoformat()}.json", spark)
    print(f"spark: {len(spark['countries'])} zones, "
          f"TTF {spark['ttf_eur_per_mwh']} EUR/MWh, "
          f"EUA {spark['eua_eur_per_tco2']} EUR/tCO2")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
