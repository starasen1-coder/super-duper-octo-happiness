#!/usr/bin/env python3
"""Exploratory XAUUSD price-channel/momentum benchmark using public M1 bid/ask OHLC.

This is a research benchmark, not a promise of profitability and not a replacement
for AMarkets MT5 tester.
"""
from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

DATA_REPO = "3650326613-png/dukascopy_xauusd_1m_data"
DATA_BRANCH = "main"
PRICE_FIELDS = ("open", "high", "low", "close")
STRATEGY = {
    "name": "H4 channel bias + M5 channel breakout/displacement",
    "H4_channel_bars": 20,
    "M5_entry_channel_bars": 12,
    "M5_ATR_period": 14,
    "minimum_signal_true_range_ATR": 0.8,
    "minimum_close_position_long": 0.75,
    "maximum_close_position_short": 0.25,
    "stop_ATR": 1.5,
    "target_R": 2.0,
    "risk_fraction_per_trade": 0.005,
    "moving_averages_in_signal": False,
    "entry": "first M1 open at the completed M5 signal close timestamp",
    "intrabar_ambiguity": "if SL and TP are both touched in an M1 bar, assume SL first",
}


def month_range(start: str, end: str) -> list[str]:
    """Return inclusive YYYY-MM month labels."""
    first = pd.Period(start, freq="M")
    last = pd.Period(end, freq="M")
    if first > last:
        raise ValueError("start month must not be after end month")
    return [str(p) for p in pd.period_range(first, last, freq="M")]


def download_month(side: str, month: str, cache_dir: Path, retries: int = 4) -> Path:
    if side not in ("bid", "ask"):
        raise ValueError(f"unsupported price side: {side}")
    file_name = f"xauusd_{side}_m1_{month.replace('-', '_')}.csv"
    destination = cache_dir / side / file_name
    if destination.exists() and destination.stat().st_size > 100:
        return destination

    url = (
        f"https://raw.githubusercontent.com/{DATA_REPO}/{DATA_BRANCH}/"
        f"xauusd/{side}/m1/{file_name}"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SMC-Research-Backtest/1.0"})
            with urllib.request.urlopen(req, timeout=90) as response:
                payload = response.read()
            if len(payload) < 100 or not payload.startswith(b"timestamp,"):
                raise ValueError(f"unexpected/empty CSV payload from {url}")
            temp = destination.with_suffix(destination.suffix + ".part")
            temp.write_bytes(payload)
            temp.replace(destination)
            return destination
        except (OSError, urllib.error.URLError, ValueError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 12))
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def load_side(side: str, months: list[str], cache_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for n, month in enumerate(months, 1):
        path = download_month(side, month, cache_dir)
        frame = pd.read_csv(path, usecols=["timestamp", *PRICE_FIELDS])
        frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
        for name in PRICE_FIELDS:
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
        frame = frame.dropna(subset=["timestamp", *PRICE_FIELDS])
        frame["timestamp"] = frame["timestamp"].astype("int64")
        frame = frame.drop_duplicates("timestamp", keep="last")
        frame = frame.rename(columns={name: f"{side}_{name}" for name in PRICE_FIELDS})
        frames.append(frame)
        if n % 12 == 0 or n == len(months):
            print(f"Loaded {side}: {n}/{len(months)} monthly files", flush=True)

    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    return data


def load_bid_ask(months: list[str], cache_dir: Path) -> pd.DataFrame:
    bid = load_side("bid", months, cache_dir)
    ask = load_side("ask", months, cache_dir)
    data = bid.merge(ask, on="timestamp", how="inner", validate="one_to_one")
    for side in ("bid", "ask"):
        o, h, l, c = (data[f"{side}_{x}"] for x in PRICE_FIELDS)
        valid_ohlc = (h >= o) & (h >= c) & (l <= o) & (l <= c) & (l > 0)
        data = data.loc[valid_ohlc]
    spread_open = data["ask_open"] - data["bid_open"]
    spread_close = data["ask_close"] - data["bid_close"]
    data = data.loc[(spread_open > 0) & (spread_close > 0)]
    data = data.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    data.index = pd.to_datetime(data.pop("timestamp"), unit="ms", utc=True)
    data.index.name = "time"
    if data.empty:
        raise ValueError("No valid inner-joined bid/ask data remains.")
    return data


def aggregate_bars(m1: pd.DataFrame, rule: str, min_minutes: int) -> pd.DataFrame:
    """Build OHLC bars from M1. Incomplete buckets below min_minutes are excluded."""
    grouped = m1.resample(rule, origin="start_day", label="left", closed="left")
    result = pd.DataFrame(index=grouped.size().index)
    for side in ("bid", "ask"):
        result[f"{side}_open"] = grouped[f"{side}_open"].first()
        result[f"{side}_high"] = grouped[f"{side}_high"].max()
        result[f"{side}_low"] = grouped[f"{side}_low"].min()
        result[f"{side}_close"] = grouped[f"{side}_close"].last()
    result["minute_count"] = grouped["bid_close"].count()
    result = result.loc[result["minute_count"] >= min_minutes]
    needed = [f"{side}_{field}" for side in ("bid", "ask") for field in PRICE_FIELDS]
    result = result.dropna(subset=needed).sort_index()
    return result


def h4_channel_bias(h4: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """Persist the last H4 breakout direction; each value becomes available at bar close."""
    previous_high = h4["bid_high"].rolling(lookback, min_periods=lookback).max().shift(1)
    previous_low = h4["bid_low"].rolling(lookback, min_periods=lookback).min().shift(1)
    close = h4["bid_close"]
    event = pd.Series(0, index=h4.index, dtype="int8")
    event.loc[close > previous_high] = 1
    event.loc[close < previous_low] = -1
    bias = event.replace(0, np.nan).ffill().fillna(0).astype("int8")
    bias.index = bias.index + pd.Timedelta(hours=4)
    return bias


def make_signals(
    m5: pd.DataFrame,
    h4_bias: pd.Series,
    channel_lookback: int = 12,
    atr_period: int = 14,
    minimum_range_atr: float = 0.8,
) -> pd.DataFrame:
    """Return signals indexed by the time the M5 bar closes (not its opening timestamp)."""
    if channel_lookback < 2 or atr_period < 2:
        raise ValueError("lookback and ATR period must be >= 2")

    high, low, close = m5["bid_high"], m5["bid_low"], m5["bid_close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = true_range.rolling(atr_period, min_periods=atr_period).mean()
    previous_high = high.rolling(channel_lookback, min_periods=channel_lookback).max().shift(1)
    previous_low = low.rolling(channel_lookback, min_periods=channel_lookback).min().shift(1)
    candle_range = (high - low).replace(0.0, np.nan)
    close_position = (close - low) / candle_range
    completed_at = m5.index + pd.Timedelta(minutes=5)
    bias = h4_bias.reindex(completed_at, method="ffill").fillna(0).to_numpy()

    long_signal = (
        (bias > 0) & (close.to_numpy() > previous_high.to_numpy()) &
        (true_range.to_numpy() >= minimum_range_atr * atr.to_numpy()) &
        (close_position.to_numpy() >= STRATEGY["minimum_close_position_long"])
    )
    short_signal = (
        (bias < 0) & (close.to_numpy() < previous_low.to_numpy()) &
        (true_range.to_numpy() >= minimum_range_atr * atr.to_numpy()) &
        (close_position.to_numpy() <= STRATEGY["maximum_close_position_short"])
    )
    signal = np.zeros(len(m5), dtype="int8")
    signal[long_signal] = 1
    signal[short_signal] = -1
    result = pd.DataFrame(
        {"signal": signal, "atr": atr.to_numpy(), "h4_bias": bias.astype("int8")},
        index=completed_at,
    )
    result.index.name = "signal_time"
    return result


def resolve_exit(position: dict, bar: dict | pd.Series, slippage: float = 0.0):
    """Pessimistic M1 stop/target resolver. Returns (price, reason) or (None, None)."""
    direction = int(position["direction"])
    side = "bid" if direction > 0 else "ask"
    open_ = float(bar[f"{side}_open"])
    high = float(bar[f"{side}_high"])
    low = float(bar[f"{side}_low"])
    stop = float(position["stop"])
    target = float(position["target"])

    if direction > 0:
        if open_ <= stop:
            return open_ - slippage, "sl_gap" if open_ < stop else "sl"
        if open_ >= target:
            return target - slippage, "tp_gap"
        if low <= stop:
            return stop - slippage, "sl"
        if high >= target:
            return target - slippage, "tp"
    else:
        if open_ >= stop:
            return open_ + slippage, "sl_gap" if open_ > stop else "sl"
        if open_ <= target:
            return target + slippage, "tp_gap"
        if high >= stop:
            return stop + slippage, "sl"
        if low <= target:
            return target + slippage, "tp"
    return None, None


def summarize_trades(trades: pd.DataFrame, risk_fraction: float = 0.005) -> dict:
    if trades.empty:
        return {
            "trades": 0, "win_rate_pct": None, "expectancy_R": None, "net_R": 0.0,
            "profit_factor_R": None, "max_drawdown_pct_model": 0.0,
            "ending_equity_index": 10000.0, "average_win_R": None, "average_loss_R": None,
            "max_consecutive_losses": 0, "by_exit_year": {},
        }
    r = trades["R"].astype(float)
    winners = r[r > 0]
    losers = r[r < 0]
    gross_wins = float(winners.sum())
    gross_losses = float(losers.sum())
    pf = gross_wins / abs(gross_losses) if gross_losses < 0 else None

    equity = 10000.0
    peak = equity
    max_dd = 0.0
    max_loss_streak = loss_streak = 0
    for ret in r:
        equity *= max(0.0, 1.0 + risk_fraction * float(ret))
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        if ret < 0:
            loss_streak += 1
            max_loss_streak = max(max_loss_streak, loss_streak)
        else:
            loss_streak = 0

    yearly = {}
    years = pd.to_datetime(trades["close_time"], utc=True).dt.year
    for year in sorted(years.unique()):
        part = trades.loc[years == year, "R"]
        pos = part[part > 0].sum()
        neg = part[part < 0].sum()
        yearly[str(int(year))] = {
            "trades": int(len(part)),
            "net_R": round(float(part.sum()), 4),
            "expectancy_R": round(float(part.mean()), 5),
            "profit_factor_R": round(float(pos / abs(neg)), 4) if neg < 0 else None,
            "win_rate_pct": round(float((part > 0).mean() * 100.0), 2),
        }
    return {
        "trades": int(len(trades)),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate_pct": round(float((r > 0).mean() * 100.0), 2),
        "expectancy_R": round(float(r.mean()), 5),
        "net_R": round(float(r.sum()), 4),
        "profit_factor_R": round(float(pf), 4) if pf is not None else None,
        "average_win_R": round(float(winners.mean()), 5) if len(winners) else None,
        "average_loss_R": round(float(losers.mean()), 5) if len(losers) else None,
        "max_drawdown_pct_model": round(float(max_dd), 4),
        "ending_equity_index": round(float(equity), 2),
        "risk_fraction_per_trade": risk_fraction,
        "max_consecutive_losses": int(max_loss_streak),
        "by_exit_year": yearly,
    }


def run_backtest(m1: pd.DataFrame, signals: pd.DataFrame, slippage: float = 0.0) -> pd.DataFrame:
    """One position max; market entry at signal-time M1 open; all exits use correct quote side."""
    if slippage < 0:
        raise ValueError("slippage cannot be negative")
    minute_index = m1.index
    entry_signals = signals.loc[signals["signal"] != 0]
    signal_by_position: dict[int, tuple[int, float]] = {}
    for signal_time, signal_row in entry_signals.iterrows():
        pos_index = minute_index.get_indexer([signal_time])[0]
        if pos_index >= 0 and pos_index < len(m1) - 1:
            atr = float(signal_row["atr"])
            if np.isfinite(atr) and atr > 0:
                signal_by_position[int(pos_index)] = (int(signal_row["signal"]), atr)

    values = {
        name: m1[name].to_numpy(dtype=float)
        for name in ("bid_open", "bid_high", "bid_low", "bid_close",
                     "ask_open", "ask_high", "ask_low", "ask_close")
    }
    timestamps = minute_index
    active = None
    trades: list[dict] = []

    def close_position(pos: dict, i: int, exit_price: float, reason: str):
        signed_price_move = int(pos["direction"]) * (exit_price - float(pos["entry"]))
        risk_dist = float(pos["risk_distance"])
        ret_r = signed_price_move / risk_dist
        trades.append({
            "open_time": timestamps[pos["open_i"]].isoformat(),
            "close_time": timestamps[i].isoformat(),
            "direction": "BUY" if pos["direction"] > 0 else "SELL",
            "entry_price": round(float(pos["entry"]), 5),
            "exit_price": round(float(exit_price), 5),
            "stop_price": round(float(pos["stop"]), 5),
            "target_price": round(float(pos["target"]), 5),
            "exit_reason": reason,
            "holding_minutes": round((timestamps[i] - timestamps[pos["open_i"]]).total_seconds() / 60, 2),
            "price_pnl_per_ounce": round(float(signed_price_move), 5),
            "R": round(float(ret_r), 6),
            "slippage_price_per_side": float(slippage),
        })

    for i in range(len(m1)):
        exited_this_bar = False
        if active is not None:
            bar = {key: values[key][i] for key in values}
            exit_price, reason = resolve_exit(active, bar, slippage)
            if exit_price is not None:
                close_position(active, i, exit_price, reason)
                active = None
                exited_this_bar = True

        if active is None and not exited_this_bar and i in signal_by_position and i < len(m1) - 1:
            direction, atr = signal_by_position[i]
            entry = values["ask_open"][i] + slippage if direction > 0 else values["bid_open"][i] - slippage
            risk_distance = float(atr) * STRATEGY["stop_ATR"]
            if entry > 0 and risk_distance > 0:
                active = {
                    "direction": direction,
                    "open_i": i,
                    "entry": float(entry),
                    "risk_distance": risk_distance,
                    "stop": float(entry - direction * risk_distance),
                    "target": float(entry + direction * risk_distance * STRATEGY["target_R"]),
                }
                bar = {key: values[key][i] for key in values}
                exit_price, reason = resolve_exit(active, bar, slippage)
                if exit_price is not None:
                    close_position(active, i, exit_price, reason)
                    active = None

    if active is not None:
        i = len(m1) - 1
        final_exit = values["bid_close"][i] - slippage if active["direction"] > 0 else values["ask_close"][i] + slippage
        close_position(active, i, final_exit, "end_of_data")

    return pd.DataFrame(trades)


def run_research(start_month: str, end_month: str, data_dir: Path, output_dir: Path) -> dict:
    months = month_range(start_month, end_month)
    prices = load_bid_ask(months, data_dir / "raw")
    spread = prices["ask_close"] - prices["bid_close"]
    m5 = aggregate_bars(prices, "5min", min_minutes=5)
    h4 = aggregate_bars(prices, "4h", min_minutes=180)
    if len(m5) < 1000 or len(h4) < 30:
        raise ValueError(f"Insufficient data after aggregation: M5={len(m5)}, H4={len(h4)}")

    bias = h4_channel_bias(h4, STRATEGY["H4_channel_bars"])
    signals = make_signals(m5, bias, STRATEGY["M5_entry_channel_bars"],
                           STRATEGY["M5_ATR_period"], STRATEGY["minimum_signal_true_range_ATR"])
    scenarios = {}
    trade_ledgers = {}
    for label, extra_slippage in (
        ("bid_ask_only_no_extra_slippage", 0.0),
        ("cost_stress_0_05_usd_per_side", 0.05),
    ):
        trades = run_backtest(prices, signals, extra_slippage)
        trade_ledgers[label] = trades
        scenarios[label] = summarize_trades(trades, STRATEGY["risk_fraction_per_trade"])

    output_dir.mkdir(parents=True, exist_ok=True)
    for label, trades in trade_ledgers.items():
        trades.to_csv(output_dir / f"trades_{label}.csv", index=False)

    result = {
        "title": "XAUUSD price-channel/momentum benchmark — exploratory, not a profitability claim",
        "data_source": f"https://github.com/{DATA_REPO}",
        "data_range_requested": {"start_month": start_month, "end_month": end_month},
        "data_range_actual": {"start": prices.index.min().isoformat(), "end": prices.index.max().isoformat()},
        "merged_bid_ask_m1_rows": int(len(prices)),
        "complete_m5_bars": int(len(m5)),
        "h4_bars_with_at_least_180_minutes": int(len(h4)),
        "median_bid_ask_close_spread_usd": round(float(spread.median()), 5),
        "p95_bid_ask_close_spread_usd": round(float(spread.quantile(0.95)), 5),
        "strategy": STRATEGY,
        "execution_assumptions": {
            "long_entry": "ask open + slippage",
            "long_exit": "bid OHLC, with adverse slippage",
            "short_entry": "bid open - slippage",
            "short_exit": "ask OHLC, with adverse slippage",
            "spread": "bid/ask quote series is used directly",
            "commission": "not included; broker-specific contract/account pricing is unavailable",
            "swap": "not included; broker-specific swap rules are unavailable",
            "money": "equity index assumes 0.5% of model equity risked per trade; not an MT5 account/margin simulation",
            "bar_ambiguity": "if SL and TP are both touched in an M1 bar, resolve_exit assumes stop first",
        },
        "scenarios": scenarios,
        "research_warning": (
            "Historical exploratory study only. Rules are fixed in source, but this interval has been viewed "
            "during the broader research. It is not a pristine holdout. Positive results, if any, require a future "
            "locked evaluation interval and verification in MT5 with broker costs, margin, swaps and contract specs."
        ),
    }
    (output_dir / "research_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2015-01", help="inclusive first month, YYYY-MM")
    parser.add_argument("--end", default="2026-08", help="inclusive last month, YYYY-MM")
    parser.add_argument("--data-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("out"))
    args = parser.parse_args()
    result = run_research(args.start, args.end, args.data_dir, args.output_dir)
    print(json.dumps({
        "actual_range": result["data_range_actual"],
        "merged_m1": result["merged_bid_ask_m1_rows"],
        "spread_median_usd": result["median_bid_ask_close_spread_usd"],
        "scenarios": result["scenarios"],
        "warning": result["research_warning"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
