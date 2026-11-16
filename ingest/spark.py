"""Clean spark spread for a CCGT.

    clean_spark = power - TTF / eta - CO2_INTENSITY * EUA
        eta           = 0.49 (CCGT thermal efficiency)
        CO2_INTENSITY = 0.37 tCO2 per MWh_elec

All inputs in EUR/MWh (EUA is EUR/tCO2 but the intensity coefficient lands
the term in EUR/MWh_elec). Output is EUR/MWh_elec of gross margin.
"""
from __future__ import annotations

GAS_EFFICIENCY = 0.49  # CCGT thermal efficiency (dimensionless); modern plants ~49-55%
CO2_INTENSITY = 0.37   # tCO2 per MWh_elec

def compute_clean_spark(
    prices: list[float | None], ttf: float, eua: float
) -> list[float | None]:
    """Clean spark spread (EUR/MWh_elec) for one zone's hourly prices."""
    fuel = ttf / GAS_EFFICIENCY + CO2_INTENSITY * eua
    return [None if p is None else p - fuel for p in prices]
