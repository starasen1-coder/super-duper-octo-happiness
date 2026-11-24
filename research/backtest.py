"""Small deterministic bar-based execution model with explicit spread."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class TradeSpec:
    sl_distance: float
    tp_distance: float
    slippage: float = 0.0


@dataclass(frozen=True)
class TradeResult:
    entry_index: int
    exit_index: int
    exit_reason: str
    entry_price: float
    exit_price: float
    net_price_move: float


def backtest_long(bars: pd.DataFrame, entry_index: int, spec: TradeSpec) -> TradeResult:
    if spec.sl_distance <= 0 or spec.tp_distance <= 0:
        raise ValueError("SL/TP distances must be positive")
    if spec.slippage < 0:
        raise ValueError("slippage must be non-negative")
    if entry_index < 0 or entry_index >= len(bars):
        raise IndexError("entry_index out of range")
    row = bars.iloc[entry_index]
    spread = float(row["spread"])
    mid_entry = float(row["open"])
    entry = mid_entry + spread / 2.0 + spec.slippage
    sl = mid_entry - spec.sl_distance
    tp = mid_entry + spec.tp_distance
    for i in range(entry_index, len(bars)):
        r = bars.iloc[i]
        bar_spread = float(r["spread"])
        bid_open = float(r["open"]) - bar_spread / 2.0
        bid_high = float(r["high"]) - bar_spread / 2.0
        bid_low = float(r["low"]) - bar_spread / 2.0

        # A stop/target crossed by the opening quote is filled at that quote,
        # not at the now-unavailable requested level.
        if bid_open <= sl:
            exit_price = bid_open - spec.slippage
            return TradeResult(entry_index, i, "sl_gap", entry, exit_price, exit_price - entry)
        if bid_open >= tp:
            exit_price = bid_open - spec.slippage
            return TradeResult(entry_index, i, "tp_gap", entry, exit_price, exit_price - entry)

        hit_sl = bid_low <= sl
        hit_tp = bid_high >= tp
        if hit_sl and hit_tp:
            # Conservative assumption: adverse level is hit first when intrabar order is unknown.
            exit_price = sl - spec.slippage
            return TradeResult(entry_index, i, "sl", entry, exit_price, exit_price - entry)
        if hit_sl:
            exit_price = sl - spec.slippage
            return TradeResult(entry_index, i, "sl", entry, exit_price, exit_price - entry)
        if hit_tp:
            exit_price = tp - spec.slippage
            return TradeResult(entry_index, i, "tp", entry, exit_price, exit_price - entry)
    last = bars.iloc[-1]
    exit_price = float(last["close"]) - float(last["spread"]) / 2.0 - spec.slippage
    return TradeResult(entry_index, len(bars)-1, "eod", entry, exit_price, exit_price - entry)
