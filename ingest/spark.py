"""Clean dark spark spread per the locked formula.

    clean_dark = power - 0.49 * TTF - 0.37 * EUA

Units: all three inputs in EUR/MWh (EUA is EUR/tCO2 but 0.37 is the tCO2/MWh
coefficient, so the term lands in EUR/MWh). Output is EUR/MWh of gross margin
for a modern CCGT burning gas at TTF.
"""
from __future__ import annotations

GAS_HEAT_RATE = 0.49   # MWh_gas per MWh_elec (CCGT ~49% efficiency inverse)
CO2_INTENSITY = 0.37   # tCO2 per MWh_elec

def compute_clean_dark(
    prices: list[float | None], ttf: float, eua: float
) -> list[float | None]:
    """Vectorised clean-dark spread for one zone's hourly prices."""
    fuel = GAS_HEAT_RATE * ttf + CO2_INTENSITY * eua
    return [None if p is None else p - fuel for p in prices]
