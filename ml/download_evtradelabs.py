"""Download public EV Trading Labs XAUUSD M5 archives and export canonical CSV.

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
CANONICAL_COLUMNS = [
    "timestamp", "bid_open", "bid_high", "bid_low", "bid_close",
    "ask_open", "ask_high", "ask_low", "ask_close", "volume",
    "spread_open", "spread_close", "spread_mean_ohlc",
]


def download_year(year: int, output: Path | None = None, url: str | None = None) -> pd.DataFrame:
    """Download and convert one calendar year, preserving invalid and duplicate rows."""
    if year < 2003:
        raise ValueError("EV Trading Labs XAUUSD M5 archive coverage starts in 2003")
    source_url = url or ARCHIVE_URL.format(year=year)
    request = Request(source_url, headers={"User-Agent": "XAUUSD-historical-data-research/1.0"})
    with urlopen(request, timeout=120) as response:
        compressed = response.read()
    try:
        payload = json.loads(gzip.decompress(compressed))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Downloaded {year} archive is not a valid gzip JSON file") from exc

    if isinstance(payload, dict):
        payload = payload.get("data", payload.get("bars", payload))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{year} archive must contain a non-empty JSON array of candles")

    raw = pd.DataFrame(payload)
    required = ["ts", "o", "h", "l", "c", "ao", "ah", "al", "ac"]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"{year} archive schema missing columns: {missing}")

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

    # Keep malformed timestamps and duplicate rows visible to the validator.
    out = out.sort_values("timestamp", na_position="last").reset_index(drop=True)
    valid_years = sorted(out["timestamp"].dropna().dt.year.unique().tolist())
    unexpected_years = [value for value in valid_years if value != year]
    if unexpected_years:
        raise ValueError(f"{year} archive contains candles stamped in other years: {unexpected_years}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return out


def download_range(start_year: int, end_year: int, output: Path) -> pd.DataFrame:
    """Download consecutive annual archives and combine without silently deduplicating."""
    if start_year < 2003:
        raise ValueError("EV Trading Labs XAUUSD M5 archive coverage starts in 2003")
    if end_year < start_year:
        raise ValueError("End year must be greater than or equal to start year")

    annual_frames = []
    for year in range(start_year, end_year + 1):
        frame = download_year(year)
        if frame.empty:
            raise RuntimeError(f"No XAUUSD M5 candles returned for {year}")
        annual_frames.append(frame)
        print(f"{year}: rows={len(frame):,}")

    combined = pd.concat(annual_frames, ignore_index=True)
    combined = combined.sort_values("timestamp", na_position="last").reset_index(drop=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None, help="Download one calendar year")
    parser.add_argument("--from-year", type=int, default=None, help="First year, inclusive")
    parser.add_argument("--to-year", type=int, default=None, help="Last year, inclusive")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.year is not None and (args.from_year is not None or args.to_year is not None):
        parser.error("--year cannot be combined with --from-year/--to-year")
    if args.year is not None:
        start_year = end_year = args.year
    elif args.from_year is None and args.to_year is None:
        start_year = end_year = 2025
    elif args.from_year is None or args.to_year is None:
        parser.error("Both --from-year and --to-year are required for a range")
    else:
        start_year, end_year = args.from_year, args.to_year

    default_name = (
        f"data/XAUUSD_M5_BID_ASK_{start_year}.csv"
        if start_year == end_year
        else f"data/XAUUSD_M5_BID_ASK_{start_year}_{end_year}.csv"
    )
    output = Path(args.output or default_name)
    result = download_range(start_year, end_year, output)
    print(f"Saved {len(result):,} rows to {output}")
    if len(result):
        print(f"UTC range: {result.timestamp.min()} .. {result.timestamp.max()}")
        print(f"Median open spread: {result.spread_open.median():.5f} USD")
        print(f"95th percentile open spread: {result.spread_open.quantile(.95):.5f} USD")


if __name__ == "__main__":
    main()
