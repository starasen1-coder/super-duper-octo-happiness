"""Download XAUUSD M5 Bid and Ask candles from Dukascopy via dukascopy-node.

Requires Node.js/npm and Python pandas. Downloads in yearly chunks and combines
matching Bid/Ask bars. Timestamps are UTC. Spread columns are price differences,
not broker points.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile
import pandas as pd


def _run_side(start: str, end: str, side: str, target: Path) -> pd.DataFrame:
    with tempfile.TemporaryDirectory(prefix=f"xauusd_{side}_") as tmp:
        cmd = [
            "npx", "--yes", "dukascopy-node",
            "-i", "xauusd", "-from", start, "-to", end,
            "-t", "m5", "-p", side, "-v", "true",
            "-f", "csv", "-dir", tmp, "-r", "3", "-rp", "1500",
        ]
        subprocess.run(cmd, check=True)
        files = sorted(Path(tmp).glob("*.csv"))
        if len(files) != 1:
            raise RuntimeError(f"Expected one {side} CSV for {start}..{end}, found {len(files)}")
        df = pd.read_csv(files[0])
    required = {"timestamp", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"Unexpected Dukascopy {side} schema: {list(df.columns)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).drop_duplicates("timestamp").sort_values("timestamp")
    rename = {c: f"{side}_{c}" for c in ("open", "high", "low", "close", "volume") if c in df.columns}
    return df[["timestamp", *rename.keys()]].rename(columns=rename)


def download(start_year: int, end_year: int, output: Path) -> pd.DataFrame:
    if start_year < 2003 or end_year < start_year:
        raise ValueError("Dukascopy XAUUSD M5 coverage starts in 2003; end year must be >= start year")
    chunks = []
    for year in range(start_year, end_year + 1):
        start, end = f"{year}-01-01", f"{year}-12-31"
        bid = _run_side(start, end, "bid", output)
        ask = _run_side(start, end, "ask", output)
        merged = bid.merge(ask, on="timestamp", how="inner", validate="one_to_one")
        if merged.empty:
            raise RuntimeError(f"No matched Bid/Ask M5 candles for {year}")
        merged["spread_open"] = merged.ask_open - merged.bid_open
        merged["spread_close"] = merged.ask_close - merged.bid_close
        merged["spread_mean_ohlc"] = (
            (merged.ask_open + merged.ask_high + merged.ask_low + merged.ask_close) / 4
            - (merged.bid_open + merged.bid_high + merged.bid_low + merged.bid_close) / 4
        )
        chunks.append(merged)
        print(f"{year}: matched Bid/Ask candles={len(merged):,}")
    result = pd.concat(chunks, ignore_index=True)
    result = result.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    if (result[["spread_open", "spread_close"]] < 0).any().any():
        raise ValueError("Negative Bid/Ask spread found; inspect source data")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-year", type=int, default=2015)
    ap.add_argument("--to-year", type=int, default=2025)
    ap.add_argument("--output", default="data/XAUUSD_M5_BID_ASK_2015_2025.csv")
    args = ap.parse_args()
    result = download(args.from_year, args.to_year, Path(args.output))
    print(f"Saved {len(result):,} bars to {args.output}")
    print(f"UTC range: {result.timestamp.min()} .. {result.timestamp.max()}")
    print(f"Median open spread: {result.spread_open.median():.5f} USD")
    print(f"95th percentile open spread: {result.spread_open.quantile(.95):.5f} USD")


if __name__ == "__main__":
    main()
