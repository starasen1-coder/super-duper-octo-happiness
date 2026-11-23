"""Leakage-safe H1 structure + M5 liquidity sweep/impulse signal."""
from __future__ import annotations
import pandas as pd
import numpy as np

def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.shift(1).rolling(period, min_periods=period).mean()

def _h1_direction(h1: pd.DataFrame, lookback: int) -> pd.DataFrame:
    x = h1.sort_values("time").copy()
    prev_high = x["high"].shift(1).rolling(lookback, min_periods=lookback).max()
    prev_low = x["low"].shift(1).rolling(lookback, min_periods=lookback).min()
    x["h1_bull"] = x["close"] > prev_high
    x["h1_bear"] = x["close"] < prev_low
    return x[["time", "h1_bull", "h1_bear"]]

def build_signals(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    liquidity_lookback: int = 36,
    structure_lookback: int = 6,
    atr_period: int = 14,
    impulse_atr: float = 1.4,
    body_ratio_min: float = 0.65,
    h1_structure_lookback: int = 5,
) -> pd.DataFrame:
    if liquidity_lookback < 2 or structure_lookback < 2 or atr_period < 2:
        raise ValueError("lookbacks must be >= 2")
    x = m5.sort_values("time").copy()
    h = _h1_direction(h1, h1_structure_lookback)
    x = pd.merge_asof(x, h.sort_values("time"), on="time", direction="backward")
    x["atr"] = _atr(x, atr_period)
    x["body_ratio"] = (x["close"] - x["open"]).abs() / (x["high"] - x["low"]).replace(0, np.nan)
    prior_high = x["high"].shift(1).rolling(liquidity_lookback, min_periods=liquidity_lookback).max()
    prior_low = x["low"].shift(1).rolling(liquidity_lookback, min_periods=liquidity_lookback).min()
    x["sweep_high"] = (x["high"] > prior_high) & (x["close"] < prior_high)
    x["sweep_low"] = (x["low"] < prior_low) & (x["close"] > prior_low)
    x["bull_impulse"] = ((x["close"] - x["open"]) > impulse_atr * x["atr"]) & (x["body_ratio"] >= body_ratio_min)
    x["bear_impulse"] = ((x["open"] - x["close"]) > impulse_atr * x["atr"]) & (x["body_ratio"] >= body_ratio_min)
    prior_structure_high = x["high"].shift(1).rolling(structure_lookback, min_periods=structure_lookback).max()
    prior_structure_low = x["low"].shift(1).rolling(structure_lookback, min_periods=structure_lookback).min()
    x["bull_confirm"] = x["close"] > prior_structure_high
    x["bear_confirm"] = x["close"] < prior_structure_low
    x["raw_long"] = x["h1_bull"].fillna(False) & x["sweep_low"] & x["bull_impulse"] & x["bull_confirm"]
    x["raw_short"] = x["h1_bear"].fillna(False) & x["sweep_high"] & x["bear_impulse"] & x["bear_confirm"]
    x["entry"] = (x["raw_long"] | x["raw_short"]).shift(1).fillna(False).astype(int)
    x["side"] = np.where(x["raw_long"].shift(1).fillna(False), 1, np.where(x["raw_short"].shift(1).fillna(False), -1, 0))
    return x
