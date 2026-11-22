"""Leakage-aware OHLCV research harness for the XAUUSD liquidity setup.

CSV columns: time, open, high, low, close; volume/tick_volume and spread optional.
Signals are evaluated only on completed bars. Entries occur at the next bar open.
If SL and TP are both touched in one candle, SL is assumed first (conservative).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    aliases = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in aliases]
    if missing:
        raise ValueError(f"Missing OHLC columns: {missing}")
    time_col = next((aliases[k] for k in ("time", "datetime", "date", "timestamp") if k in aliases), None)
    if time_col is None:
        raise ValueError("CSV must contain time/datetime/date/timestamp")
    out = pd.DataFrame({k: pd.to_numeric(df[aliases[k]], errors="coerce") for k in required})
    out["time"] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    vol_col = next((aliases[k] for k in ("tick_volume", "volume", "vol") if k in aliases), None)
    spr_col = next((aliases[k] for k in ("spread", "spread_points") if k in aliases), None)
    out["volume"] = pd.to_numeric(df[vol_col], errors="coerce") if vol_col else 0.0
    out["spread"] = pd.to_numeric(df[spr_col], errors="coerce") if spr_col else 0.0
    out = out.dropna(subset=["time", *required]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if len(out) < 100:
        raise ValueError("At least 100 valid bars are required")
    if (out["high"] < out["low"]).any() or (out["close"] <= 0).any():
        raise ValueError("Invalid OHLC values")
    return out


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high-prev).abs(), (df.low-prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def build_events(df: pd.DataFrame, lookback: int = 36, atr_period: int = 14,
                 impulse_atr: float = 1.4, body_ratio: float = 0.65,
                 horizon: int = 48, rr: float = 2.0) -> pd.DataFrame:
    """Create candidate rows and first-touch labels; all features use data <= event bar."""
    if lookback < 10 or horizon < 1 or rr <= 0:
        raise ValueError("Invalid lookback, horizon or RR")
    d = df.copy().reset_index(drop=True)
    d["atr"] = _atr(d, atr_period)
    prior_hi = d.high.shift(1).rolling(lookback, min_periods=lookback).max()
    prior_lo = d.low.shift(1).rolling(lookback, min_periods=lookback).min()
    rng = d.high - d.low
    body = (d.close - d.open).abs() / rng.replace(0, np.nan)
    # Sweep + reclaim on a completed candle, followed by a directional impulse.
    bull = (d.low < prior_lo) & (d.close > prior_lo) & (d.close > d.open)
    bear = (d.high > prior_hi) & (d.close < prior_hi) & (d.close < d.open)
    impulse = (rng >= d.atr * impulse_atr) & (body >= body_ratio)
    direction = np.where(bull & impulse, 1, np.where(bear & impulse, -1, 0))
    events = []
    for i in np.flatnonzero(direction):
        if i + 1 >= len(d) or not np.isfinite(d.atr.iloc[i]) or d.atr.iloc[i] <= 0:
            continue
        side = int(direction[i])
        entry = float(d.open.iloc[i+1])
        # Stop is beyond the sweep wick, with a small ATR buffer.
        sl = float((d.low.iloc[i] if side == 1 else d.high.iloc[i]) + (-side) * d.atr.iloc[i] * 0.10)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + side * risk * rr
        # Entry-bar gap may already invalidate the setup; do not silently backfill.
        if (side == 1 and entry <= sl) or (side == -1 and entry >= sl):
            continue
        label = np.nan
        exit_i = -1
        for j in range(i+1, min(i+1+horizon, len(d))):
            hit_sl = d.low.iloc[j] <= sl if side == 1 else d.high.iloc[j] >= sl
            hit_tp = d.high.iloc[j] >= tp if side == 1 else d.low.iloc[j] <= tp
            if hit_sl or hit_tp:
                label = 0 if hit_sl else 1  # stop-first when both touched
                exit_i = j
                break
        if np.isnan(label):
            continue  # censored observations are not forced into the negative class
        hist = d.iloc[max(0, i-19):i+1]
        close = float(d.close.iloc[i])
        events.append({
            "event_index": i, "entry_index": i+1, "exit_index": exit_i,
            "time": d.time.iloc[i], "direction": side, "entry": entry, "sl": sl, "tp": tp,
            "atr": float(d.atr.iloc[i]), "range_atr": float(rng.iloc[i]/d.atr.iloc[i]),
            "body_ratio": float(body.iloc[i]), "sweep_depth_atr": float(
                (prior_lo.iloc[i]-d.low.iloc[i] if side == 1 else d.high.iloc[i]-prior_hi.iloc[i])/d.atr.iloc[i]),
            "return_1_atr": float((close-d.close.iloc[i-1])/d.atr.iloc[i]) if i else 0.0,
            "vol_rel": float(d.volume.iloc[i]/max(hist.volume.mean(), 1.0)),
            "label": int(label), "risk": risk, "rr": rr,
        })
    return pd.DataFrame(events)


def simulate(events: pd.DataFrame, probabilities: np.ndarray | None = None,
             threshold: float = 0.60, cost_r: float = 0.0) -> dict:
    if events.empty:
        return {"trades": 0, "win_rate": 0.0, "expectancy_r": 0.0, "profit_factor": 0.0, "max_dd_r": 0.0, "net_r": 0.0}
    use = np.ones(len(events), dtype=bool) if probabilities is None else np.asarray(probabilities) >= threshold
    sample = events.loc[use]
    if sample.empty:
        return {"trades": 0, "win_rate": 0.0, "expectancy_r": 0.0, "profit_factor": 0.0, "max_dd_r": 0.0, "net_r": 0.0}
    gross = np.where(sample.label.to_numpy() == 1, sample.rr.to_numpy(), -1.0)
    net = gross - float(cost_r)
    equity = np.cumsum(net)
    peak = np.maximum.accumulate(np.r_[0.0, equity])
    dd = peak[1:] - equity
    wins = net[net > 0].sum()
    losses = -net[net < 0].sum()
    return {
        "trades": int(len(net)),
        "win_rate": float((net > 0).mean()),
        "expectancy_r": float(net.mean()),
        "profit_factor": float(wins / losses) if losses > 0 else (None if wins > 0 else 0.0),
        "max_dd_r": float(dd.max(initial=0.0)),
        "net_r": float(net.sum()),
    }


def compare(events: pd.DataFrame, predictions: pd.DataFrame | None = None,
            threshold: float = 0.60, cost_r: float = 0.0) -> dict:
    result = {"baseline": simulate(events, cost_r=cost_r)}
    if predictions is not None:
        if not {"event_index", "probability"}.issubset(predictions.columns):
            raise ValueError("predictions.csv requires event_index,probability")
        merged = events.merge(predictions, on="event_index", how="inner", validate="one_to_one")
        result["ml_filter"] = simulate(merged, merged.probability.to_numpy(), threshold, cost_r)
        result["matched_baseline"] = simulate(merged, cost_r=cost_r)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--predictions", default=None, help="Out-of-fold predictions only; event_index,probability")
    ap.add_argument("--out", default="research_output")
    ap.add_argument("--horizon", type=int, default=48)
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--threshold", type=float, default=0.60)
    ap.add_argument("--cost-r", type=float, default=0.0, help="Round-trip costs expressed in R units")
    args = ap.parse_args()
    data = load_ohlcv(args.csv)
    events = build_events(data, horizon=args.horizon, rr=args.rr)
    pred = pd.read_csv(args.predictions) if args.predictions else None
    report = compare(events, pred, args.threshold, args.cost_r)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    events.to_csv(out / "events.csv", index=False)
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"bars": len(data), "events": len(events), "report": report}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
