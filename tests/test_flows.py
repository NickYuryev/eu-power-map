from datetime import datetime

from ingest.energy_charts import FlowCountry, FlowSeries
from ingest.flows import build_pairs, pair_key
from ingest.labels import BRUSSELS, hour_labels


def test_pair_key_is_alphabetical():
    assert pair_key("DE", "FR") == pair_key("FR", "DE") == "DE-FR"


def test_sign_normalises_to_first_iso():
    # DE's /cbpf says it imports 1.5 GW from France all day (positive to DE).
    # That means physical flow is FR -> DE, so under key "DE-FR" (DE first)
    # the stored flow (DE -> FR) must be negative.
    day = datetime(2026, 6, 15, tzinfo=BRUSSELS)
    secs = [int((day.replace(hour=h)).timestamp()) for h in range(24)]
    de = FlowSeries(
        unix_seconds=secs,
        countries=[
            FlowCountry(name="France", data=[1.5] * 24),  # GW import to DE
            FlowCountry(name="sum", data=[1.5] * 24),
        ],
    )
    out = build_pairs({"DE": de, "FR": de}, hour_labels(day.date()))
    # 1.5 GW import to DE => DE->FR = -1500 MW
    assert out["DE-FR"][12] == -1500.0
