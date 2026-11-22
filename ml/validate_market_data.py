"""Validate downloaded XAUUSD M5 Bid/Ask history and report spread/gap quality."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd


def validate(path: str | Path) -> dict:
    d = pd.read_csv(path, parse_dates=["timestamp"])
    required = [
        "timestamp", "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close", "spread_open", "spread_close",
    ]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    d["timestamp"] = pd.to_datetime(d.timestamp, utc=True, errors="coerce")
    d = d.dropna(subset=["timestamp"]).sort_values("timestamp")
    duplicates = int(d.timestamp.duplicated().sum())
    bid_bad = int(((d.bid_high < d.bid_low) | (d.bid_open > d.bid_high) |
                   (d.bid_open < d.bid_low) | (d.bid_close > d.bid_high) |
                   (d.bid_close < d.bid_low)).sum())
    ask_bad = int(((d.ask_high < d.ask_low) | (d.ask_open > d.ask_high) |
                   (d.ask_open < d.ask_low) | (d.ask_close > d.ask_high) |
                   (d.ask_close < d.ask_low)).sum())
    negative_spread = int(((d.spread_open < 0) | (d.spread_close < 0)).sum())
    delta = d.timestamp.diff().dt.total_seconds().div(60)
    # Report all gaps > 5 minutes. Weekends and market closures are not auto-classified as faults.
    gaps = delta[delta > 5]
    spread = d.spread_open
    return {
        "rows": int(len(d)),
        "first_utc": str(d.timestamp.min()),
        "last_utc": str(d.timestamp.max()),
        "duplicate_timestamps": duplicates,
        "invalid_bid_ohlc_rows": bid_bad,
        "invalid_ask_ohlc_rows": ask_bad,
        "negative_spread_rows": negative_spread,
        "gaps_over_5m": int(len(gaps)),
        "median_open_spread_usd": float(spread.median()),
        "p95_open_spread_usd": float(spread.quantile(.95)),
        "max_open_spread_usd": float(spread.max()),
        "verdict": "PASS" if len(d) and not duplicates and not bid_bad and not ask_bad and not negative_spread else "FAIL",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    report = validate(args.csv)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json:
        Path(args.json).write_text(rendered, encoding="utf-8")
    if report["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
