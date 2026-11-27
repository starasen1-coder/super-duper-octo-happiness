"""Leakage-safe H1 structure + M5 liquidity sweep/impulse signal."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .order_flow import order_flow_features, order_flow_confirmation
from .quote_liquidity import merge_quote_liquidity


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
    # H1 timestamps denote candle OPEN. Its close-based structure state is only
    # observable one hour later; exposing it at the open leaks the H1 close.
    x["available_at"] = x["time"] + pd.Timedelta(hours=1)
    return x[["available_at", "h1_bull", "h1_bear"]]


def build_signals(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    liquidity_lookback: int = 36,
    structure_lookback: int = 6,
    atr_period: int = 14,
    impulse_atr: float = 1.4,
    body_ratio_min: float = 0.65,
    h1_structure_lookback: int = 5,
    order_flow_mode: str = "auto",
    delta_z_min: float = 1.0,
    quote_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if liquidity_lookback < 2 or structure_lookback < 2 or atr_period < 2:
        raise ValueError("lookbacks must be >= 2")
    x = m5.sort_values("time").copy()
    h = _h1_direction(h1, h1_structure_lookback)
    # M5 timestamps denote candle OPEN; decisions are made at that M5 candle CLOSE.
    x["_decision_time"] = x["time"] + pd.Timedelta(minutes=5)
    x = pd.merge_asof(
        x.sort_values("_decision_time"),
        h.sort_values("available_at"),
        left_on="_decision_time",
        right_on="available_at",
        direction="backward",
    )
    x = x.drop(columns=["_decision_time"])
    if quote_features is not None:
        x = merge_quote_liquidity(x, quote_features)
    x = order_flow_features(x, mode=order_flow_mode)
    x["flow_confirm"] = order_flow_confirmation(x, delta_z_min=delta_z_min)
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
    x["h1_bull"] = x["h1_bull"].fillna(False).astype(bool)
    x["h1_bear"] = x["h1_bear"].fillna(False).astype(bool)
    x["raw_long"] = x["h1_bull"] & x["sweep_low"] & x["bull_impulse"] & x["bull_confirm"] & (x["flow_confirm"] == 1)
    x["raw_short"] = x["h1_bear"] & x["sweep_high"] & x["bear_impulse"] & x["bear_confirm"] & (x["flow_confirm"] == -1)
    prior_long = x["raw_long"].astype("boolean").shift(1).fillna(False).astype(bool)
    prior_short = x["raw_short"].astype("boolean").shift(1).fillna(False).astype(bool)
    x["entry"] = (prior_long | prior_short).astype(int)
    x["side"] = np.where(prior_long, 1, np.where(prior_short, -1, 0))
    return x



def build_retest_setups(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    liquidity_lookback: int = 36,
    structure_lookback: int = 6,
    atr_period: int = 14,
    impulse_atr: float = 1.4,
    body_ratio_min: float = 0.65,
    impulse_window: int = 4,
    retest_window: int = 6,
    h1_structure_lookback: int = 5,
    risk_reward: float = 2.0,
) -> pd.DataFrame:
    """Build sequential sweep -> displacement/BOS -> OB retest setups.

    M5/H1 timestamps are candle-open times. The H1 direction is joined at the
    M5 retest close, and an entry is placed at the following M5 open.
    This is a deterministic research signal generator, not an order executor.
    """
    if min(liquidity_lookback, structure_lookback, atr_period,
           impulse_window, retest_window, h1_structure_lookback) < 2:
        raise ValueError("lookbacks and windows must be >= 2")
    if impulse_atr <= 0 or not 0 < body_ratio_min <= 1 or risk_reward <= 0:
        raise ValueError("impulse_atr/risk_reward must be positive and body_ratio_min in (0, 1]")
    required = {"time", "open", "high", "low", "close"}
    if not required.issubset(m5.columns) or not required.issubset(h1.columns):
        raise ValueError("M5 and H1 data require time/open/high/low/close columns")

    x = m5.copy()
    x["time"] = pd.to_datetime(x["time"], utc=True, errors="coerce")
    if x["time"].isna().any():
        raise ValueError("invalid M5 timestamps")
    x = x.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)

    h = h1.copy()
    h["time"] = pd.to_datetime(h["time"], utc=True, errors="coerce")
    if h["time"].isna().any():
        raise ValueError("invalid H1 timestamps")
    h = _h1_direction(h, h1_structure_lookback)
    x["_decision_time"] = x["time"] + pd.Timedelta(minutes=5)
    x = pd.merge_asof(
        x.sort_values("_decision_time"),
        h.sort_values("available_at"),
        left_on="_decision_time",
        right_on="available_at",
        direction="backward",
    ).reset_index(drop=True)

    atr = _atr(x, atr_period)
    candle_range = (x["high"] - x["low"]).replace(0, np.nan)
    body_ratio = (x["close"] - x["open"]).abs() / candle_range
    pool_high = x["high"].shift(1).rolling(
        liquidity_lookback, min_periods=liquidity_lookback
    ).max()
    pool_low = x["low"].shift(1).rolling(
        liquidity_lookback, min_periods=liquidity_lookback
    ).min()
    structure_high = x["high"].shift(1).rolling(
        structure_lookback, min_periods=structure_lookback
    ).max()
    structure_low = x["low"].shift(1).rolling(
        structure_lookback, min_periods=structure_lookback
    ).min()

    x["h1_bull"] = x["h1_bull"].fillna(False).astype(bool)
    x["h1_bear"] = x["h1_bear"].fillna(False).astype(bool)
    setups: list[dict] = []
    last_entry_index = -1
    n = len(x)

    for sweep_idx in range(n - 2):
        if sweep_idx <= last_entry_index:
            continue
        long_sweep = (
            pd.notna(pool_low.iloc[sweep_idx])
            and x["low"].iloc[sweep_idx] < pool_low.iloc[sweep_idx]
            and x["close"].iloc[sweep_idx] > pool_low.iloc[sweep_idx]
        )
        short_sweep = (
            pd.notna(pool_high.iloc[sweep_idx])
            and x["high"].iloc[sweep_idx] > pool_high.iloc[sweep_idx]
            and x["close"].iloc[sweep_idx] < pool_high.iloc[sweep_idx]
        )
        if not long_sweep and not short_sweep:
            continue
        side = 1 if long_sweep else -1

        found = False
        impulse_end = min(sweep_idx + impulse_window, n - 2)
        for impulse_idx in range(sweep_idx + 1, impulse_end + 1):
            a = atr.iloc[impulse_idx]
            if pd.isna(a) or a <= 0:
                continue
            displacement = x["high"].iloc[impulse_idx] - x["low"].iloc[impulse_idx]
            body = body_ratio.iloc[impulse_idx]
            if pd.isna(body) or displacement < impulse_atr * a or body < body_ratio_min:
                continue

            if side == 1:
                bos_level = structure_high.iloc[impulse_idx]
                valid_impulse = (
                    x["close"].iloc[impulse_idx] > x["open"].iloc[impulse_idx]
                    and pd.notna(bos_level)
                    and x["close"].iloc[impulse_idx] > bos_level
                )
                opposing = x.index[
                    (x.index >= sweep_idx) & (x.index < impulse_idx)
                    & (x["close"] < x["open"])
                ]
            else:
                bos_level = structure_low.iloc[impulse_idx]
                valid_impulse = (
                    x["close"].iloc[impulse_idx] < x["open"].iloc[impulse_idx]
                    and pd.notna(bos_level)
                    and x["close"].iloc[impulse_idx] < bos_level
                )
                opposing = x.index[
                    (x.index >= sweep_idx) & (x.index < impulse_idx)
                    & (x["close"] > x["open"])
                ]
            if not valid_impulse or len(opposing) == 0:
                continue

            ob_idx = int(opposing[-1])
            ob_high = float(x["high"].iloc[ob_idx])
            ob_low = float(x["low"].iloc[ob_idx])
            retest_end = min(impulse_idx + retest_window, n - 2)
            for retest_idx in range(impulse_idx + 1, retest_end + 1):
                if side == 1:
                    aligned = bool(x["h1_bull"].iloc[retest_idx])
                    touched = (
                        x["low"].iloc[retest_idx] <= ob_high
                        and x["high"].iloc[retest_idx] >= ob_low
                    )
                    rejected = (
                        x["close"].iloc[retest_idx] > ob_high
                        and x["close"].iloc[retest_idx] > x["open"].iloc[retest_idx]
                    )
                else:
                    aligned = bool(x["h1_bear"].iloc[retest_idx])
                    touched = (
                        x["high"].iloc[retest_idx] >= ob_low
                        and x["low"].iloc[retest_idx] <= ob_high
                    )
                    rejected = (
                        x["close"].iloc[retest_idx] < ob_low
                        and x["close"].iloc[retest_idx] < x["open"].iloc[retest_idx]
                    )
                if not (aligned and touched and rejected):
                    continue

                entry_idx = retest_idx + 1
                entry_price = float(x["open"].iloc[entry_idx])
                stop_price = ob_low if side == 1 else ob_high
                risk = entry_price - stop_price if side == 1 else stop_price - entry_price
                if risk <= 0:
                    continue
                target_price = (
                    entry_price + risk_reward * risk
                    if side == 1 else entry_price - risk_reward * risk
                )
                setups.append({
                    "side": side,
                    "sweep_index": sweep_idx,
                    "sweep_time": x["time"].iloc[sweep_idx],
                    "sweep_level": float(pool_low.iloc[sweep_idx] if side == 1 else pool_high.iloc[sweep_idx]),
                    "impulse_index": impulse_idx,
                    "impulse_time": x["time"].iloc[impulse_idx],
                    "bos_level": float(bos_level),
                    "ob_index": ob_idx,
                    "ob_high": ob_high,
                    "ob_low": ob_low,
                    "retest_index": retest_idx,
                    "retest_time": x["time"].iloc[retest_idx],
                    "entry_index": entry_idx,
                    "entry_time": x["time"].iloc[entry_idx],
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "risk": risk,
                })
                last_entry_index = entry_idx
                found = True
                break
            if found:
                break

    return pd.DataFrame(setups, columns=[
        "side", "sweep_index", "sweep_time", "sweep_level",
        "impulse_index", "impulse_time", "bos_level", "ob_index",
        "ob_high", "ob_low", "retest_index", "retest_time",
        "entry_index", "entry_time", "entry_price", "stop_price",
        "target_price", "risk",
    ])
