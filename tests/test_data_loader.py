import pandas as pd
import pytest

from research.data_loader import merge_spread, merge_bid_ask_ohlcv


def test_merge_spread_rejects_stale_quote_after_market_gap():
    price = pd.DataFrame({
        "time": pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"]),
        "open": [100.0, 101.0], "high": [101.0, 102.0],
        "low": [99.0, 100.0], "close": [100.5, 101.5],
    })
    spread = pd.DataFrame({
        "time": pd.to_datetime(["2026-01-01T00:00:00Z"]),
        "spread": [0.2],
    })
    with pytest.raises(ValueError, match="stale spread"):
        merge_spread(price, spread)


def test_merge_bid_ask_builds_mid_ohlc_and_open_spread():
    bid = pd.DataFrame({
        "DateTime": ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"],
        "Open": [100.0, 101.0], "High": [102.0, 103.0],
        "Low": [99.0, 100.0], "Close": [101.0, 102.0],
        "Tick Volume": [10, 20],
    })
    ask = pd.DataFrame({
        "DateTime": ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"],
        "Open": [100.2, 101.3], "High": [102.2, 103.3],
        "Low": [99.2, 100.3], "Close": [101.2, 102.3],
        "Tick Volume": [11, 21],
    })
    out = merge_bid_ask_ohlcv(bid, ask)
    assert out.loc[0, "open"] == pytest.approx(100.1)
    assert out.loc[0, "close"] == pytest.approx(101.1)
    assert out.loc[0, "spread"] == pytest.approx(0.2)
    assert out.loc[1, "spread"] == pytest.approx(0.3)


def test_merge_bid_ask_rejects_unsynchronized_bars():
    bid = pd.DataFrame({
        "time": ["2026-01-01T00:00:00Z"],
        "open": [100], "high": [101], "low": [99], "close": [100],
    })
    ask = pd.DataFrame({
        "time": ["2026-01-01T00:05:00Z"],
        "open": [100.2], "high": [101.2], "low": [99.2], "close": [100.2],
    })
    with pytest.raises(ValueError, match="timestamps do not match"):
        merge_bid_ask_ohlcv(bid, ask)
