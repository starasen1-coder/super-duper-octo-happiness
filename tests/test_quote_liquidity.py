import pandas as pd
import pytest

from research.quote_liquidity import aggregate_quote_liquidity, merge_quote_liquidity


def test_quote_volume_imbalance_is_not_trade_delta():
    ticks = pd.DataFrame({
        "timestamp": [1767225600000, 1767225601000, 1767225901000],
        "askPrice": [100.1, 100.1, 100.2],
        "bidPrice": [99.9, 99.9, 100.0],
        "askVolume": [3.0, 1.0, 4.0],
        "bidVolume": [1.0, 3.0, 2.0],
    })
    out = aggregate_quote_liquidity(ticks)
    assert out["quote_imbalance"].tolist() == pytest.approx([0.0, -1 / 3])
    assert out["mean_spread"].tolist() == pytest.approx([0.2, 0.2])
    assert out["flow_semantics"].eq("quoted_liquidity_not_trade_flow").all()
    assert out["time"].tolist() == list(pd.to_datetime(["2026-01-01T00:05:00Z", "2026-01-01T00:10:00Z"]))


def test_invalid_quote_volume_and_crossed_market_rejected():
    ticks = pd.DataFrame({
        "timestamp": [1767225600000], "askPrice": [99.0], "bidPrice": [100.0],
        "askVolume": [-1.0], "bidVolume": [1.0],
    })
    with pytest.raises(ValueError):
        aggregate_quote_liquidity(ticks)


def test_quote_features_merge_only_after_bar_close():
    bars = pd.DataFrame({
        "time": pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z", "2026-01-01T00:10:00Z"]),
        "close": [1, 2, 3],
    })
    quote = pd.DataFrame({
        "time": pd.to_datetime(["2026-01-01T00:05:00Z", "2026-01-01T00:07:00Z"]),
        "quote_imbalance": [0.25, -0.5],
    })
    out = merge_quote_liquidity(bars, quote)
    assert out["quote_imbalance"].iloc[:2].tolist() == [0.25, -0.5]
    assert out["quote_imbalance"].iloc[2] == -0.5
