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


def merge_bid_ask_ohlcv(
    bid: pd.DataFrame,
    ask: pd.DataFrame,
) -> pd.DataFrame:
    """Build mid OHLC and price-unit spread from synchronized Bid/Ask bars.

    Exact timestamp matching is required: unmatched bars are rejected rather
    than silently dropped or forward-filled. Spread is measured at bar open,
    matching the execution model's entry quote convention.
    """
    b = normalize_ohlcv(bid).rename(columns={
        "open": "bid_open", "high": "bid_high", "low": "bid_low",
        "close": "bid_close", "volume": "bid_volume",
    })
    a = normalize_ohlcv(ask).rename(columns={
        "open": "ask_open", "high": "ask_high", "low": "ask_low",
        "close": "ask_close", "volume": "ask_volume",
    })
    joined = b.merge(a, on="time", how="outer", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        missing_bid = int(joined["_merge"].eq("right_only").sum())
        missing_ask = int(joined["_merge"].eq("left_only").sum())
        raise ValueError(
            f"Bid/Ask timestamps do not match exactly: {missing_bid} Ask-only, "
            f"{missing_ask} Bid-only bars"
        )
    joined = joined.drop(columns="_merge")
    if (joined["ask_open"] < joined["bid_open"]).any() or (
        joined["ask_close"] < joined["bid_close"]
    ).any():
        raise ValueError("negative Bid/Ask spread at bar open or close")
    out = pd.DataFrame({
        "time": joined["time"],
        "open": (joined["bid_open"] + joined["ask_open"]) / 2.0,
        "high": (joined["bid_high"] + joined["ask_high"]) / 2.0,
        "low": (joined["bid_low"] + joined["ask_low"]) / 2.0,
        "close": (joined["bid_close"] + joined["ask_close"]) / 2.0,
        "volume": joined["bid_volume"],
        "spread": joined["ask_open"] - joined["bid_open"],
        "spread_close": joined["ask_close"] - joined["bid_close"],
    })
    if (out["spread"] < 0).any() or (out["spread_close"] < 0).any():
        raise ValueError("negative spread encountered")
    return out.reset_index(drop=True)


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
