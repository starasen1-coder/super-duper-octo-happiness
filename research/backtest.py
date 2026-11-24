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



def backtest_short(bars: pd.DataFrame, entry_index: int, spec: TradeSpec) -> TradeResult:
    """Conservative short execution against Ask quotes derived from mid bars + spread."""
    if spec.sl_distance <= 0 or spec.tp_distance <= 0:
        raise ValueError("SL/TP distances must be positive")
    if spec.slippage < 0:
        raise ValueError("slippage must be non-negative")
    if entry_index < 0 or entry_index >= len(bars):
        raise IndexError("entry_index out of range")

    row = bars.iloc[entry_index]
    spread = float(row["spread"])
    mid_entry = float(row["open"])
    entry = mid_entry - spread / 2.0 - spec.slippage
    sl = mid_entry + spec.sl_distance
    tp = mid_entry - spec.tp_distance

    for i in range(entry_index, len(bars)):
        r = bars.iloc[i]
        bar_spread = float(r["spread"])
        ask_open = float(r["open"]) + bar_spread / 2.0
        ask_high = float(r["high"]) + bar_spread / 2.0
        ask_low = float(r["low"]) + bar_spread / 2.0

        # A gap is filled at the first available Ask, not at the skipped level.
        if ask_open >= sl:
            exit_price = ask_open + spec.slippage
            return TradeResult(entry_index, i, "sl_gap", entry, exit_price, entry - exit_price)
        if ask_open <= tp:
            exit_price = ask_open + spec.slippage
            return TradeResult(entry_index, i, "tp_gap", entry, exit_price, entry - exit_price)

        hit_sl = ask_high >= sl
        hit_tp = ask_low <= tp
        if hit_sl and hit_tp:
            # Conservative assumption: adverse level is hit first when intrabar order is unknown.
            exit_price = sl + spec.slippage
            return TradeResult(entry_index, i, "sl", entry, exit_price, entry - exit_price)
        if hit_sl:
            exit_price = sl + spec.slippage
            return TradeResult(entry_index, i, "sl", entry, exit_price, entry - exit_price)
        if hit_tp:
            exit_price = tp + spec.slippage
            return TradeResult(entry_index, i, "tp", entry, exit_price, entry - exit_price)

    last = bars.iloc[-1]
    exit_price = float(last["close"]) + float(last["spread"]) / 2.0 + spec.slippage
    return TradeResult(entry_index, len(bars) - 1, "eod", entry, exit_price, entry - exit_price)



def backtest_setups(
    bars: pd.DataFrame,
    setups: pd.DataFrame,
    slippage: float = 0.0,
    horizon: int = 48,
) -> pd.DataFrame:
    """Execute sequential long/short setup rows with no overlapping positions.

    OHLC columns are assumed to be mid prices and spread is a price-unit value.
    The entry is on the next bar open; the execution helpers use Ask for long
    entries/exits and Bid for short entries/exits. Commission and swap are not
    included and must be modeled separately.
    """
    required_bars = {"open", "high", "low", "close", "spread"}
    required_setups = {"side", "entry_index", "stop_price", "target_price"}
    if not required_bars.issubset(bars.columns):
        raise ValueError(f"bars require columns: {', '.join(sorted(required_bars))}")
    if not required_setups.issubset(setups.columns):
        raise ValueError(f"setups require columns: {', '.join(sorted(required_setups))}")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if slippage < 0:
        raise ValueError("slippage must be non-negative")
    if setups.empty:
        return pd.DataFrame(columns=[
            "side", "entry_index", "exit_index", "exit_reason",
            "entry_price", "exit_price", "net_price_move", "initial_risk", "r_multiple",
        ])

    results: list[dict] = []
    last_exit_index = -1
    ordered = setups.sort_values("entry_index", kind="stable")
    for _, setup in ordered.iterrows():
        side = int(setup["side"])
        entry_index = int(setup["entry_index"])
        if side not in (-1, 1):
            raise ValueError("setup side must be 1 (long) or -1 (short)")
        if entry_index <= last_exit_index:
            continue
        if entry_index < 0 or entry_index >= len(bars):
            raise IndexError("setup entry_index out of range")

        mid_entry = float(bars.iloc[entry_index]["open"])
        stop = float(setup["stop_price"])
        target = float(setup["target_price"])
        risk = mid_entry - stop if side == 1 else stop - mid_entry
        reward = target - mid_entry if side == 1 else mid_entry - target
        if risk <= 0 or reward <= 0:
            raise ValueError("setup stop/target levels are invalid for its side")

        window_end = min(len(bars), entry_index + horizon)
        window = bars.iloc[:window_end]
        spec = TradeSpec(
            sl_distance=risk,
            tp_distance=reward,
            slippage=slippage,
        )
        result = (
            backtest_long(window, entry_index, spec)
            if side == 1 else backtest_short(window, entry_index, spec)
        )
        row = setup.to_dict()
        row.update({
            "entry_index": result.entry_index,
            "exit_index": result.exit_index,
            "exit_reason": result.exit_reason,
            "entry_price": result.entry_price,
            "exit_price": result.exit_price,
            "net_price_move": result.net_price_move,
            "initial_risk": risk,
            "r_multiple": result.net_price_move / risk,
        })
        results.append(row)
        last_exit_index = result.exit_index

    return pd.DataFrame(results)
