"""Causal structural-liquidity targets for historical research.
Only pivots fully confirmed before the entry bar are eligible. No future bars are inspected.
"""
from __future__ import annotations
import pandas as pd

def nearest_confirmed_liquidity_target(bars: pd.DataFrame, entry_index: int, side: int, lookback: int = 288, pivot_left: int = 2, pivot_right: int = 2, after_index: int = -1) -> float | None:
    """Return nearest confirmed opposing swing level beyond the entry price.

    entry_index is the bar whose OPEN is the simulated entry. Only bars
    strictly before it may be used; all right-side pivot bars must be closed.
    """
    required = {"high", "low", "open"}
    if not required.issubset(bars.columns):
        raise ValueError("bars require high, low and open columns")
    if side not in (-1, 1):
        raise ValueError("side must be 1 (long) or -1 (short)")
    if lookback < 3 or pivot_left < 1 or pivot_right < 1:
        raise ValueError("lookback must be >=3 and pivot widths >=1")
    if entry_index < 0 or entry_index >= len(bars):
        raise IndexError("entry_index out of range")
    entry = float(bars.iloc[entry_index]["open"])
    start = max(pivot_left, entry_index - lookback, after_index + 1)
    end = entry_index - pivot_right - 1
    if end < start:
        return None
    candidates: list[float] = []
    for pivot in range(start, end + 1):
        left = bars.iloc[pivot - pivot_left:pivot]
        right = bars.iloc[pivot + 1:pivot + pivot_right + 1]
        high = float(bars.iloc[pivot]["high"])
        low = float(bars.iloc[pivot]["low"])
        if side == 1:
            is_pivot = high > float(left["high"].max()) and high >= float(right["high"].max())
            if is_pivot and high > entry:
                candidates.append(high)
        else:
            is_pivot = low < float(left["low"].min()) and low <= float(right["low"].min())
            if is_pivot and low < entry:
                candidates.append(low)
    if not candidates:
        return None
    return min(candidates) if side == 1 else max(candidates)
