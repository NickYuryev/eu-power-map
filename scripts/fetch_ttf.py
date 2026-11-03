"""Fetch the latest TTF front-month close via yfinance and write data/ttf.json.

Run as `uv run scripts/fetch_ttf.py`. TTF=F on Yahoo is the ICE Endex Dutch TTF
Natural Gas futures front month, quoted in EUR/MWh.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ttf.json"


def main() -> int:
    hist = yf.Ticker("TTF=F").history(period="7d")
    if hist.empty:
        print("TTF=F history empty", file=sys.stderr)
        return 1
    row = hist.iloc[-1]
    date = hist.index[-1].date().isoformat()
    payload = {
        "date": date,
        "close_eur_per_mwh": round(float(row["Close"]), 3),
        "source": "yfinance TTF=F",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"ttf: {payload['date']} close {payload['close_eur_per_mwh']} EUR/MWh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
