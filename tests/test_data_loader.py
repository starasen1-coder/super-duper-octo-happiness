import pandas as pd
import pytest

from research.data_loader import merge_spread


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
