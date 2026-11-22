"""Validate XAUUSD M5 Bid/Ask history, quote integrity, spread and timestamp gaps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def validate(
    path: str | Path,
    timeframe_minutes: int = 5,
    expected_from_year: int | None = None,
    expected_to_year: int | None = None,
) -> dict:
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
        if crosses_weekend and minutes >= 8 * 60:
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

    gap_kinds = ("weekend_or_weekly_close", "session_break_or_holiday", "intraday_candidate")
    gap_counts = {
        kind: sum(1 for gap in gap_rows if gap["classification"] == kind)
        for kind in gap_kinds
    }
    intraday_missing_slots = sum(
        gap["estimated_missing_m5_slots"] for gap in gap_rows
        if gap["classification"] == "intraday_candidate"
    )

    yearly_summary = []
    for year, group in d.groupby(d.timestamp.dt.year, sort=True):
        year_gaps = [
            gap for gap in gap_rows
            if pd.Timestamp(gap["from_utc"]).year == int(year)
        ]
        year_gap_counts = {
            kind: sum(1 for gap in year_gaps if gap["classification"] == kind)
            for kind in gap_kinds
        }
        yearly_spread = group.spread_open
        yearly_summary.append({
            "year": int(year),
            "rows": int(len(group)),
            "first_utc": str(group.timestamp.min()),
            "last_utc": str(group.timestamp.max()),
            "median_open_spread_usd": float(yearly_spread.median()),
            "p95_open_spread_usd": float(yearly_spread.quantile(.95)),
            "max_open_spread_usd": float(yearly_spread.max()),
            "gaps_over_timeframe": len(year_gaps),
            "gap_classification_counts": year_gap_counts,
            "intraday_candidate_missing_slots_estimate": int(sum(
                gap["estimated_missing_m5_slots"] for gap in year_gaps
                if gap["classification"] == "intraday_candidate"
            )),
        })

    available_years = sorted(item["year"] for item in yearly_summary)
    missing_calendar_years = []
    if expected_from_year is not None and expected_to_year is not None:
        if expected_to_year < expected_from_year:
            raise ValueError("Expected end year must be greater than or equal to start year")
        missing_calendar_years = sorted(
            set(range(expected_from_year, expected_to_year + 1)) - set(available_years)
        )

    spread = d.spread_open
    integrity_ok = bool(
        len(d) and invalid_timestamps == 0 and duplicates == 0 and bid_bad == 0
        and ask_bad == 0 and negative_spread == 0 and spread_mismatch == 0
        and not missing_calendar_years
    )
    return {
        "timeframe_minutes": timeframe_minutes,
        "rows": int(len(d)),
        "invalid_timestamp_rows": invalid_timestamps,
        "first_utc": str(d.timestamp.min()) if len(d) else None,
        "last_utc": str(d.timestamp.max()) if len(d) else None,
        "available_calendar_years": available_years,
        "missing_calendar_years": missing_calendar_years,
        "duplicate_timestamps": duplicates,
        "invalid_bid_ohlc_rows": bid_bad,
        "invalid_ask_ohlc_rows": ask_bad,
        "negative_spread_rows": negative_spread,
        "spread_quote_mismatch_rows": spread_mismatch,
        "gaps_over_timeframe": len(gap_rows),
        "gap_classification_counts": gap_counts,
        "intraday_candidate_missing_slots_estimate": int(intraday_missing_slots),
        "largest_gaps": sorted(gap_rows, key=lambda gap: gap["gap_minutes"], reverse=True)[:20],
        "intraday_candidate_gaps": [
            gap for gap in gap_rows if gap["classification"] == "intraday_candidate"
        ],
        "median_open_spread_usd": float(spread.median()) if len(d) else None,
        "p95_open_spread_usd": float(spread.quantile(.95)) if len(d) else None,
        "max_open_spread_usd": float(spread.max()) if len(d) else None,
        "yearly_summary": yearly_summary,
        "verdict": "PASS" if integrity_ok else "FAIL",
        "gap_review": "REVIEW" if gap_counts["intraday_candidate"] else "NO_INTRADAY_GAPS_FLAGGED",
    }


def render_markdown(report: dict) -> str:
    """Render a concise human-readable report from the validator's JSON result."""
    lines = [
        "# XAUUSD M5 Bid/Ask — 2015–2025 data quality report",
        "",
        "Source: EV Trading Labs public annual archives, derived from Dukascopy data.",
        "Catalogue: https://evtradelabs.com/data",
        "Attribution: EV Trading Labs.",
        "",
        "This is a data-integrity report, not a strategy backtest or profitability assessment.",
        "",
        "## Combined dataset",
        "",
        f"- Rows: {report['rows']:,}",
        f"- UTC range: {report['first_utc']} to {report['last_utc']}",
        f"- Calendar years present: {', '.join(map(str, report['available_calendar_years']))}",
        f"- Missing expected calendar years: {report['missing_calendar_years'] or 'none'}",
        f"- Quote integrity verdict: **{report['verdict']}**",
        f"- Gaps requiring review: **{report['gap_review']}**",
        "",
        "## Year-by-year spread and gap statistics",
        "",
        "| Year | M5 rows | Median spread ($) | P95 spread ($) | Max spread ($) | Gaps >5m | Short-gap candidates |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["yearly_summary"]:
        counts = item["gap_classification_counts"]
        lines.append(
            f"| {item['year']} | {item['rows']:,} | {item['median_open_spread_usd']:.4f} "
            f"| {item['p95_open_spread_usd']:.4f} | {item['max_open_spread_usd']:.4f} "
            f"| {item['gaps_over_timeframe']:,} | {counts['intraday_candidate']:,} |"
        )
    lines.extend([
        "",
        "## Combined integrity checks",
        "",
        f"- Invalid timestamps: {report['invalid_timestamp_rows']}",
        f"- Duplicate timestamps: {report['duplicate_timestamps']}",
        f"- Invalid Bid OHLC rows: {report['invalid_bid_ohlc_rows']}",
        f"- Invalid Ask OHLC rows: {report['invalid_ask_ohlc_rows']}",
        f"- Negative spread rows: {report['negative_spread_rows']}",
        f"- Spread arithmetic mismatches: {report['spread_quote_mismatch_rows']}",
        "",
        "## Gap classification",
        "",
        f"- Weekend / weekly closure intervals: {report['gap_classification_counts']['weekend_or_weekly_close']}",
        f"- Session / holiday intervals: {report['gap_classification_counts']['session_break_or_holiday']}",
        f"- Short intraday candidates: {report['gap_classification_counts']['intraday_candidate']}",
        f"- Estimated missing M5 slots in short candidates: {report['intraday_candidate_missing_slots_estimate']}",
        "",
        "Short gaps are candidates for source-calendar review, not proof of missing provider candles. "
        "Do not interpolate synthetic bars into the source history.",
        "",
        "## Limitations",
        "",
        "- Bid and Ask OHLC bars are separately aggregated; bar-open and bar-close spreads are estimates, not tick-synchronized intrabar spreads.",
        "- Provider volume is not centralized exchange traded volume.",
        "- This is Dukascopy-derived reference history, not AMarkets broker history.",
        "- Extreme spreads must be reviewed, not replaced with a constant spread.",
        "- Historical data quality does not establish strategy profitability.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument("--markdown", default=None)
    parser.add_argument("--timeframe-minutes", type=int, default=5)
    parser.add_argument("--expected-from-year", type=int, default=None)
    parser.add_argument("--expected-to-year", type=int, default=None)
    args = parser.parse_args()
    report = validate(
        args.csv,
        args.timeframe_minutes,
        args.expected_from_year,
        args.expected_to_year,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json:
        Path(args.json).write_text(rendered, encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    if report["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
