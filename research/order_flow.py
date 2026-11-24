"""Order-flow features from bid/ask or candle proxy data.

True aggressor order flow requires tick/trade data. When only OHLCV is available,
the module exposes a clearly named candle-proxy mode rather than pretending that
tick volume is true buy/sell volume.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def true_order_flow(
    bid_volume: pd.Series,
    ask_volume: pd.Series,
) -> pd.Series:
    """Net aggressive flow proxy when bid/ask classified volumes are available."""
    b = pd.to_numeric(bid_volume, errors="coerce").fillna(0.0)
    a = pd.to_numeric(ask_volume, errors="coerce").fillna(0.0)
    return a - b

def volume_delta_proxy(df: pd.DataFrame) -> pd.Series:
    """OHLCV-only proxy: signed volume by candle direction.

    This is NOT true order flow. It is retained only as a fallback for datasets
    without bid/ask classified trade volume.
    """
    volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    sign = np.sign(df["close"] - df["open"])
    return volume * sign

def cumulative_delta(delta: pd.Series) -> pd.Series:
    return pd.to_numeric(delta, errors="coerce").fillna(0.0).cumsum()

def delta_zscore(delta: pd.Series, lookback: int = 50) -> pd.Series:
    x = pd.to_numeric(delta, errors="coerce")
    mean = x.shift(1).rolling(lookback, min_periods=lookback).mean()
    std = x.shift(1).rolling(lookback, min_periods=lookback).std(ddof=0)
    return (x - mean) / std.replace(0, np.nan)

def order_flow_features(df: pd.DataFrame, mode: str = "auto") -> pd.DataFrame:
    """Add delta, cumulative delta and delta z-score without future leakage."""
    out = df.copy()
    if mode not in {"auto", "true", "proxy"}:
        raise ValueError("mode must be auto, true or proxy")
    has_trade_semantics = (
        "volume_semantics" in out.columns
        and out["volume_semantics"].eq("aggressor_trade_volume").all()
    )
    has_classified_volumes = {"bid_volume", "ask_volume"} <= set(out.columns)
    if mode == "true" and not (has_trade_semantics and has_classified_volumes):
        raise ValueError(
            "true order flow requires bid_volume/ask_volume explicitly labeled "
            "volume_semantics='aggressor_trade_volume'; quote sizes are not trade flow"
        )
    if mode == "true" or (mode == "auto" and has_trade_semantics and has_classified_volumes):
        out["delta"] = true_order_flow(out["bid_volume"], out["ask_volume"])
        out["order_flow_mode"] = "true"
    elif mode in {"auto", "proxy"}:
        out["delta"] = volume_delta_proxy(out)
        out["order_flow_mode"] = "proxy"
    else:
        raise ValueError("true order flow requires bid_volume and ask_volume")
    out["cum_delta"] = cumulative_delta(out["delta"])
    out["delta_z"] = delta_zscore(out["delta"])
    out["delta_abs"] = out["delta"].abs()
    return out

def order_flow_confirmation(
    df: pd.DataFrame,
    delta_z_min: float = 1.0,
) -> pd.Series:
    """Directional confirmation: positive delta for long, negative for short."""
    long_ok = (df["delta_z"] >= delta_z_min) & (df["delta"] > 0)
    short_ok = (df["delta_z"] <= -delta_z_min) & (df["delta"] < 0)
    return pd.Series(np.where(long_ok, 1, np.where(short_ok, -1, 0)), index=df.index)
