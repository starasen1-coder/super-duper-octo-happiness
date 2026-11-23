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
    x = ticks[list(required)].copy()
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
    total = out["ask_quote_volume"] + out["bid_quote_volume"]
    out["quote_imbalance"] = np.where(
        total > 0,
        (out["bid_quote_volume"] - out["ask_quote_volume"]) / total,
        0.0,
    )
    out["flow_semantics"] = "quoted_liquidity_not_trade_flow"
    return out
