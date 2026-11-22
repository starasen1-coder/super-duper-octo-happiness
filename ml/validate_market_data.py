"""Validate XAUUSD M5 Bid/Ask history, quote integrity, spread and timestamp gaps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def validate(path: str | Path, timeframe_minutes: int = 5) -> dict:
    d = pd.read_csv(path)
    required = [
        "timestamp", "bid_open", "bid_high", "bid_low", "bid_close",
        "ask_open", "ask_high", "ask_low", "ask_close", "spread_open", "spread_close",
    ]
    missing = [column for column in required if column not in d.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    parsed = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(parsed.isna().sum())
    d = d.assign(timestamp=parsed).dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    duplicates = int(d.timestamp.duplicated().sum())

    bid_bad = int(((d.bid_high < d.bid_low) | (d.bid_open > d.bid_high) |
                   (d.bid_open < d.bid_low) | (d.bid_close > d.bid_high) |
                   (d.bid_close < d.bid_low)).sum())
    ask_bad = int(((d.ask_high < d.ask_low) | (d.ask_open > d.ask_high) |
                   (d.ask_open < d.ask_low) | (d.ask_close > d.ask_high) |
                   (d.ask_close < d.ask_low)).sum())
    negative_spread = int(((d.spread_open < 0) | (d.spread_close < 0)).sum())
    open_mismatch = (d.spread_open - (d.ask_open - d.bid_open)).abs() > 1e-5
    close_mismatch = (d.spread_close - (d.ask_close - d.bid_close)).abs() > 1e-5
    spread_mismatch = int((open_mismatch | close_mismatch).sum())

    delta = d.timestamp.diff().dt.total_seconds().div(60)
    gap_rows = []
    for idx in delta[delta > timeframe_minutes].index:
        start = d.loc[idx - 1, "timestamp"]
        end = d.loc[idx, "timestamp"]
        minutes = float(delta.loc[idx])
        span_days = pd.date_range(start.normalize(), end.normalize(), freq="D")
        crosses_weekend = any(day.dayofweek >= 5 for day in span_days)
        if crosses_weekend:
            kind = "weekend_or_weekly_close"
        elif minutes > 60:
            kind = "session_break_or_holiday"
        else:
            kind = "intraday_candidate"
        missing_slots = max(0, int(round(minutes / timeframe_minutes)) - 1)
        gap_rows.append({
            "from_utc": start.isoformat(),
            "to_utc": end.isoformat(),
            "gap_minutes": round(minutes, 2),
            "estimated_missing_m5_slots": missing_slots,
            "classification": kind,
        })

    gap_counts = {
        kind: sum(1 for gap in gap_rows if gap["classification"] == kind)
        for kind in ("weekend_or_weekly_close", "session_break_or_holiday", "intraday_candidate")
    }
    intraday_missing_slots = sum(
        gap["estimated_missing_m5_slots"] for gap in gap_rows
        if gap["classification"] == "intraday_candidate"
    )
    spread = d.spread_open
    integrity_ok = bool(
        len(d) and invalid_timestamps == 0 and duplicates == 0 and bid_bad == 0
        and ask_bad == 0 and negative_spread == 0 and spread_mismatch == 0
    )
    return {
        "timeframe_minutes": timeframe_minutes,
        "rows": int(len(d)),
        "invalid_timestamp_rows": invalid_timestamps,
        "first_utc": str(d.timestamp.min()) if len(d) else None,
        "last_utc": str(d.timestamp.max()) if len(d) else None,
        "duplicate_timestamps": duplicates,
        "invalid_bid_ohlc_rows": bid_bad,
        "invalid_ask_ohlc_rows": ask_bad,
        "negative_spread_rows": negative_spread,
        "spread_quote_mismatch_rows": spread_mismatch,
        "gaps_over_timeframe": len(gap_rows),
        "gap_classification_counts": gap_counts,
        "intraday_candidate_missing_slots_estimate": int(intraday_missing_slots),
        "largest_gaps": sorted(gap_rows, key=lambda gap: gap["gap_minutes"], reverse=True)[:20],
        "median_open_spread_usd": float(spread.median()) if len(d) else None,
        "p95_open_spread_usd": float(spread.quantile(.95)) if len(d) else None,
        "max_open_spread_usd": float(spread.max()) if len(d) else None,
        "verdict": "PASS" if integrity_ok else "FAIL",
        "gap_review": "REVIEW" if gap_counts["intraday_candidate"] else "NO_INTRADAY_GAPS_FLAGGED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument("--timeframe-minutes", type=int, default=5)
    args = parser.parse_args()
    report = validate(args.csv, args.timeframe_minutes)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json:
        Path(args.json).write_text(rendered, encoding="utf-8")
    if report["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
