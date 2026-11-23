"""Aggregate quoted bid/ask liquidity; this is not executed trade flow."""
from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_quote_liquidity(ticks: pd.DataFrame, rule: str = "5min") -> pd.DataFrame:
    required = {"timestamp", "askPrice", "bidPrice", "askVolume", "bidVolume"}
    if not isinstance(ticks, pd.DataFrame) or ticks.empty:
        raise ValueError("tick data must be a non-empty DataFrame")
    missing = required - set(ticks.columns)
    if missing:
        raise ValueError(f"missing tick fields: {', '.join(sorted(missing))}")
    x = ticks[["timestamp", "askPrice", "bidPrice", "askVolume", "bidVolume"]].copy()
    x["time"] = pd.to_datetime(x.pop("timestamp"), unit="ms", utc=True, errors="coerce")
    for col in ("askPrice", "bidPrice", "askVolume", "bidVolume"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    if x.isna().any().any():
        raise ValueError("tick data contains invalid or missing values")
    if (x[["askPrice", "bidPrice"]] <= 0).any().any():
        raise ValueError("quote prices must be positive")
    if (x["askPrice"] < x["bidPrice"]).any():
        raise ValueError("crossed quote: askPrice is below bidPrice")
    if (x[["askVolume", "bidVolume"]] < 0).any().any():
        raise ValueError("quoted volumes must be non-negative")
    x["spread"] = x["askPrice"] - x["bidPrice"]
    x["bar_time"] = x["time"].dt.floor(rule)
    out = x.groupby("bar_time", sort=True).agg(
        ask_quote_volume=("askVolume", "mean"),
        bid_quote_volume=("bidVolume", "mean"),
        mean_spread=("spread", "mean"),
        median_spread=("spread", "median"),
        tick_count=("time", "size"),
    ).reset_index().rename(columns={"bar_time": "time"})
    # A bucket's features are available only after the bucket has closed.
    out["time"] = out["time"] + pd.Timedelta(rule)
    total = out["ask_quote_volume"] + out["bid_quote_volume"]
    out["quote_imbalance"] = np.where(
        total > 0,
        (out["bid_quote_volume"] - out["ask_quote_volume"]) / total,
        0.0,
    )
    out["flow_semantics"] = "quoted_liquidity_not_trade_flow"
    return out


def merge_quote_liquidity(m5: pd.DataFrame, quote_features: pd.DataFrame, bar_duration: str = "5min") -> pd.DataFrame:
    """Attach quote features only after their aggregation interval has closed.

    M5 input timestamps denote bar opens. Aggregated quote feature timestamps
    denote the end/availability time of their bucket.
    """
    if "time" not in m5 or "time" not in quote_features:
        raise ValueError("both frames require a time column")
    if "quote_imbalance" not in quote_features:
        raise ValueError("quote features require quote_imbalance")
    left = m5.copy()
    right = quote_features.copy()
    left["time"] = pd.to_datetime(left["time"], utc=True, errors="coerce")
    right["time"] = pd.to_datetime(right["time"], utc=True, errors="coerce")
    if left["time"].isna().any() or right["time"].isna().any():
        raise ValueError("invalid timestamps in quote merge")
    left["_bar_close_time"] = left["time"] + pd.Timedelta(bar_duration)
    right = right.rename(columns={"time": "quote_available_at"})
    right = right.drop(columns=[c for c in right.columns if c in left.columns and c != "quote_available_at"])
    merged = pd.merge_asof(
        left.sort_values("_bar_close_time"), right.sort_values("quote_available_at"),
        left_on="_bar_close_time", right_on="quote_available_at", direction="backward",
    )
    return merged.drop(columns=["_bar_close_time"])
