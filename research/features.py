"""Leakage-safe XAUUSD feature primitives for research.

This module is intentionally independent from MT5 and uses only closed bars.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).rolling(n, min_periods=n).mean()

def body_ratio(df: pd.DataFrame) -> pd.Series:
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (df["close"] - df["open"]).abs() / rng

def direction(df: pd.DataFrame) -> pd.Series:
    return np.sign(df["close"] - df["open"])

def impulse_score(df: pd.DataFrame, n: int = 14) -> pd.Series:
    a = atr(df, n)
    return (df["high"] - df["low"]) / a

def liquidity_pool_high(df: pd.DataFrame, lookback: int = 36) -> pd.Series:
    # Level is formed only from bars strictly before the current bar.
    return df["high"].shift(1).rolling(lookback, min_periods=lookback).max()

def liquidity_pool_low(df: pd.DataFrame, lookback: int = 36) -> pd.Series:
    return df["low"].shift(1).rolling(lookback, min_periods=lookback).min()

def sweep_high(df: pd.DataFrame, lookback: int = 36) -> pd.Series:
    level = liquidity_pool_high(df, lookback)
    return (df["high"] > level) & (df["close"] < level)

def sweep_low(df: pd.DataFrame, lookback: int = 36) -> pd.Series:
    level = liquidity_pool_low(df, lookback)
    return (df["low"] < level) & (df["close"] > level)
