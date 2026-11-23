import pandas as pd
import pytest

from research.quote_liquidity import aggregate_quote_liquidity


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


def test_invalid_quote_volume_and_crossed_market_rejected():
    ticks = pd.DataFrame({
        "timestamp": [1767225600000], "askPrice": [99.0], "bidPrice": [100.0],
        "askVolume": [-1.0], "bidVolume": [1.0],
    })
    with pytest.raises(ValueError):
        aggregate_quote_liquidity(ticks)
