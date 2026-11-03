"""Energy-Charts REST client. Keyless, CC BY 4.0 for public bidding zones.

See https://api.energy-charts.info/ . `/cbpf` returns GW (positive = import to
the queried country); `/price` returns EUR/MWh. Resolution isn't declared in
the response — infer it from the spacing of `unix_seconds`.
"""
from __future__ import annotations

from datetime import date
from typing import Self

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://api.energy-charts.info"

# One representative bidding zone per country, kept small on purpose.
# IT, DK, SE, NO have multiple price zones; we pick one for the map.
BIDDING_ZONES: dict[str, str] = {
    "DE": "DE-LU", "FR": "FR", "ES": "ES", "IT": "IT-North", "GB": "GB",
    "NL": "NL",    "BE": "BE", "AT": "AT", "CH": "CH",       "PL": "PL",
    "CZ": "CZ",    "DK": "DK1", "SE": "SE4", "NO": "NO2",    "PT": "PT",
}


class PriceSeries(BaseModel):
    unix_seconds: list[int]
    price: list[float | None]
    unit: str
    deprecated: bool = False


class FlowCountry(BaseModel):
    name: str
    data: list[float | None]


class FlowSeries(BaseModel):
    unix_seconds: list[int]
    countries: list[FlowCountry]
    deprecated: bool = False


def _is_retryable(exc: BaseException) -> bool:
    # 400 means bad bidding zone — never retry; 429 and transient errors do.
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code != 400
    return isinstance(exc, httpx.HTTPError)


_retry = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=3, max=60),
    retry=lambda s: _is_retryable(s.outcome.exception()),
)


class EnergyChartsClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._http = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "eu-power-map (+github.com/NickYuryev/eu-power-map)"},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @_retry
    def _get(self, path: str, params: dict[str, str]) -> dict:
        r = self._http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def fetch_price(self, country: str, start: date, end: date) -> PriceSeries:
        """Day-ahead prices in EUR/MWh for one country's main bidding zone."""
        bzn = BIDDING_ZONES[country]
        data = self._get(
            "/price",
            {"bzn": bzn, "start": start.isoformat(), "end": end.isoformat()},
        )
        return PriceSeries.model_validate(data)

    def fetch_cbpf(self, country: str, start: date, end: date) -> FlowSeries:
        """Physical cross-border flows for one country, in GW; +ve = import."""
        data = self._get(
            "/cbpf",
            {"country": country.lower(), "start": start.isoformat(), "end": end.isoformat()},
        )
        return FlowSeries.model_validate(data)
