"""Download public EV Trading Labs XAUUSD M5 archive and export canonical CSV.

Source: https://evtradelabs.com/data
Archive fields: ts,o,h,l,c,ao,ah,al,ac,v. ts is Unix epoch seconds (UTC).
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

ARCHIVE_URL = "https://evtradelabs.com/api/simulator/data/XAUUSD/M5/{year}.json.gz"


def download_year(year: int, output: Path, url: str | None = None) -> pd.DataFrame:
    source_url = url or ARCHIVE_URL.format(year=year)
    request = Request(source_url, headers={"User-Agent": "XAUUSD-historical-data-research/1.0"})
    with urlopen(request, timeout=90) as response:
        compressed = response.read()
    try:
        payload = json.loads(gzip.decompress(compressed))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Downloaded archive is not a valid gzip JSON file") from exc

    if isinstance(payload, dict):
        payload = payload.get("data", payload.get("bars", payload))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Archive must contain a non-empty JSON array of candles")

    raw = pd.DataFrame(payload)
    required = ["ts", "o", "h", "l", "c", "ao", "ah", "al", "ac"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"Archive schema missing columns: {missing}")

    out = pd.DataFrame({
        "timestamp": pd.to_datetime(pd.to_numeric(raw["ts"], errors="coerce"),
                                    unit="s", utc=True, errors="coerce"),
        "bid_open": pd.to_numeric(raw["o"], errors="coerce"),
        "bid_high": pd.to_numeric(raw["h"], errors="coerce"),
        "bid_low": pd.to_numeric(raw["l"], errors="coerce"),
        "bid_close": pd.to_numeric(raw["c"], errors="coerce"),
        "ask_open": pd.to_numeric(raw["ao"], errors="coerce"),
        "ask_high": pd.to_numeric(raw["ah"], errors="coerce"),
        "ask_low": pd.to_numeric(raw["al"], errors="coerce"),
        "ask_close": pd.to_numeric(raw["ac"], errors="coerce"),
    })
    out["volume"] = pd.to_numeric(raw["v"], errors="coerce") if "v" in raw.columns else 0.0
    out["spread_open"] = out["ask_open"] - out["bid_open"]
    out["spread_close"] = out["ask_close"] - out["bid_close"]
    out["spread_mean_ohlc"] = (
        (out["ask_open"] + out["ask_high"] + out["ask_low"] + out["ask_close"]) / 4
        - (out["bid_open"] + out["bid_high"] + out["bid_low"] + out["bid_close"]) / 4
    )
    # Preserve duplicate and invalid rows so the validator can report them.
    out = out.sort_values("timestamp", na_position="last").reset_index(drop=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--output", default="data/XAUUSD_M5_BID_ASK_2025.csv")
    parser.add_argument("--url", default=None, help="Optional alternate archive URL")
    args = parser.parse_args()
    result = download_year(args.year, Path(args.output), args.url)
    print(f"Saved {len(result):,} raw rows to {args.output}")
    print(f"Invalid timestamps: {int(result.timestamp.isna().sum())}")
    print(f"Negative open spreads: {int((result.spread_open < 0).sum())}")
    print("Run ml.validate_market_data to inspect the full report.")


if __name__ == "__main__":
    main()
