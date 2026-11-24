"""Leakage-safe market data normalization for MT5 research datasets."""
from __future__ import annotations
import pandas as pd

_OHLC_ALIASES = {
    "time": ["time", "datetime", "date", "timestamp", "date_time"],
    "open": ["open", "o"],
    "high": ["high", "h"],
    "low": ["low", "l"],
    "close": ["close", "c"],
    "volume": ["volume", "tick volume", "tick_volume", "real volume", "real_volume"],
}
_SPREAD_ALIASES = ["spread", "spread_points", "spreadpoint", "spread_price", "bid_ask_spread"]

def _find(df: pd.DataFrame, aliases: list[str]) -> str | None:
    norm = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
    for a in aliases:
        key = a.lower().replace(" ", "_")
        if key in norm:
            return norm[key]
    return None

def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("OHLCV data must be a non-empty DataFrame")
    cols = {}
    for target, aliases in _OHLC_ALIASES.items():
        source = _find(df, aliases)
        if source is None and target != "volume":
            raise ValueError(f"missing required column: {target}")
        if source is not None:
            cols[target] = source
    out = df[[cols[k] for k in cols]].copy()
    out.columns = list(cols)
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    if out["time"].isna().any():
        raise ValueError("invalid timestamps")
    for c in ["open", "high", "low", "close", "volume"]:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError("OHLC contains non-numeric or missing values")
    if (out["high"] < out[["open", "close"]].max(axis=1)).any() or (out["low"] > out[["open", "close"]].min(axis=1)).any():
        raise ValueError("invalid OHLC: high/low do not contain open/close")
    out = out.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    if "volume" not in out:
        out["volume"] = 0.0
    return out[["time", "open", "high", "low", "close", "volume"]]

def normalize_spread(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("spread data must be a non-empty DataFrame")
    t = _find(df, _OHLC_ALIASES["time"])
    s = _find(df, _SPREAD_ALIASES)
    if t is None or s is None:
        raise ValueError("spread data requires time and spread columns")
    out = pd.DataFrame({"time": pd.to_datetime(df[t], utc=True, errors="coerce"),
                        "spread": pd.to_numeric(df[s], errors="coerce")})
    if out["time"].isna().any() or out["spread"].isna().any():
        raise ValueError("invalid spread data")
    if (out["spread"] < 0).any():
        raise ValueError("spread contains negative values")
    return out.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)

def merge_spread(
    ohlcv: pd.DataFrame,
    spread: pd.DataFrame,
    max_age: str | pd.Timedelta = "5min",
) -> pd.DataFrame:
    """Attach only a recent, already-known spread quote to each price bar.

    The default 5-minute freshness bound is appropriate for M5 inputs. Callers
    using another timeframe must choose an explicit, suitable max_age.
    """
    price = normalize_ohlcv(ohlcv)
    spr = normalize_spread(spread)
    tolerance = pd.Timedelta(max_age)
    if tolerance <= pd.Timedelta(0):
        raise ValueError("max_age must be positive")
    out = pd.merge_asof(
        price.sort_values("time"),
        spr.sort_values("time"),
        on="time",
        direction="backward",
        tolerance=tolerance,
    )
    if out["spread"].isna().any():
        raise ValueError(
            "missing or stale spread quote: spread coverage is incomplete "
            f"within max_age={tolerance}"
        )
    return out
