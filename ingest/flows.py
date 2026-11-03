"""Physical cross-border flows between pairs of our 15 countries.

Energy-Charts' /cbpf returns, for one source country, one series per neighbour
in GW with positive meaning import INTO that source. We normalise to:
  - MW
  - signed value where positive = flow from the alphabetically-first ISO code
    toward the second (so "AT-DE" = positive is Austria -> Germany).

A pair is kept the first time we see it. The second response for the same pair
is ignored — the two sides often agree within a few MW on Energy-Charts.
"""
from __future__ import annotations

from .bucket import to_hourly
from .energy_charts import FlowSeries

# Full English names Energy-Charts emits, mapped to ISO-2.
NAME_TO_ISO: dict[str, str] = {
    "Germany": "DE", "France": "FR", "Spain": "ES", "Italy": "IT",
    "Great Britain": "GB", "United Kingdom": "GB",
    "Netherlands": "NL", "Belgium": "BE", "Austria": "AT",
    "Switzerland": "CH", "Poland": "PL",
    "Czech Republic": "CZ", "Czechia": "CZ",
    "Denmark": "DK", "Sweden": "SE", "Norway": "NO", "Portugal": "PT",
}


def pair_key(a: str, b: str) -> str:
    return "-".join(sorted((a, b)))


def _signed(src: str, dst: str, mw: float | None) -> float | None:
    """Rewrite an import-to-src value as flow (first_iso -> second_iso)."""
    if mw is None:
        return None
    first, _ = sorted((src, dst))
    return -mw if src == first else mw


def build_pairs(
    responses: dict[str, FlowSeries],
    hour_labels: list[str],
) -> dict[str, list[float | None]]:
    """Return {pair_key: hourly MW aligned to hour_labels, first-ISO positive}."""
    out: dict[str, list[float | None]] = {}
    for src, series in responses.items():
        for neighbour in series.countries:
            if neighbour.name == "sum":
                continue
            dst = NAME_TO_ISO.get(neighbour.name)
            if not dst or dst not in responses:
                continue
            key = pair_key(src, dst)
            if key in out:
                continue  # first side wins
            mw = [None if v is None else v * 1000 for v in neighbour.data]
            hourly = to_hourly(series.unix_seconds, mw)
            aligned = [_signed(src, dst, hourly.get(h)) for h in hour_labels]
            out[key] = aligned
    return out
