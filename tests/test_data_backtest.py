import pandas as pd
import pytest

from research.data_loader import normalize_ohlcv, normalize_spread


def test_normalize_ohlcv_accepts_common_columns_and_sorts():
    raw = pd.DataFrame({
        "DateTime": ["2026-01-01 00:01:00", "2026-01-01 00:00:00"],
        "Open": [101, 100], "High": [102, 101], "Low": [99, 98], "Close": [100.5, 99.5],
        "Tick Volume": [20, 10],
    })
    out = normalize_ohlcv(raw)
    assert list(out.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert out["time"].is_monotonic_increasing
    assert out.iloc[0]["volume"] == 10


def test_normalize_spread_rejects_negative_values():
    raw = pd.DataFrame({"DateTime": ["2026-01-01"], "Spread": [-1]})
    with pytest.raises(ValueError, match="negative"):
        normalize_spread(raw)


def test_backtest_spread_is_charged_on_entry_and_exit():
    from research.backtest import TradeSpec, backtest_long

    bars = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC"),
        "open": [100.0, 100.0, 100.0],
        "high": [100.0, 101.2, 101.2],
        "low": [100.0, 99.8, 99.8],
        "close": [100.0, 101.0, 101.0],
        "spread": [0.2, 0.2, 0.2],
    })
    result = backtest_long(bars, entry_index=0, spec=TradeSpec(sl_distance=0.5, tp_distance=1.0))
    assert result.exit_reason == "tp"
    assert result.net_price_move == pytest.approx(0.9)


def test_long_stop_gap_fills_at_first_available_bid_not_stale_stop_level():
    from research.backtest import TradeSpec, backtest_long

    bars = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=2, freq="5min", tz="UTC"),
        "open": [100.0, 98.0],
        "high": [100.1, 98.2],
        "low": [99.9, 97.8],
        "close": [100.0, 98.1],
        "spread": [0.2, 0.2],
    })
    result = backtest_long(
        bars, entry_index=0,
        spec=TradeSpec(sl_distance=0.5, tp_distance=1.0, slippage=0.05),
    )
    assert result.exit_reason == "sl_gap"
    assert result.exit_index == 1
    assert result.exit_price == pytest.approx(97.85)


def test_long_target_gap_fills_at_first_available_bid():
    from research.backtest import TradeSpec, backtest_long

    bars = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=2, freq="5min", tz="UTC"),
        "open": [100.0, 102.0],
        "high": [100.1, 102.2],
        "low": [99.9, 101.8],
        "close": [100.0, 102.1],
        "spread": [0.2, 0.2],
    })
    result = backtest_long(
        bars, entry_index=0,
        spec=TradeSpec(sl_distance=0.5, tp_distance=1.0, slippage=0.05),
    )
    assert result.exit_reason == "tp_gap"
    assert result.exit_index == 1
    assert result.exit_price == pytest.approx(101.85)


def test_short_execution_charges_spread_and_returns_positive_profit_for_target():
    import research.backtest as execution

    assert callable(getattr(execution, "backtest_short", None))
    bars = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=2, freq="5min", tz="UTC"),
        "open": [100.0, 100.0], "high": [100.0, 100.2],
        "low": [100.0, 98.8], "close": [100.0, 99.0],
        "spread": [0.2, 0.2],
    })
    result = execution.backtest_short(
        bars, entry_index=0,
        spec=execution.TradeSpec(sl_distance=1.0, tp_distance=1.0),
    )
    assert result.exit_reason == "tp"
    assert result.net_price_move == pytest.approx(0.9)


def test_short_stop_gap_fills_at_first_available_ask():
    import research.backtest as execution

    assert callable(getattr(execution, "backtest_short", None))
    bars = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=2, freq="5min", tz="UTC"),
        "open": [100.0, 102.0], "high": [100.1, 102.2],
        "low": [99.9, 101.8], "close": [100.0, 102.1],
        "spread": [0.2, 0.2],
    })
    result = execution.backtest_short(
        bars, entry_index=0,
        spec=execution.TradeSpec(sl_distance=1.0, tp_distance=1.0, slippage=0.05),
    )
    assert result.exit_reason == "sl_gap"
    assert result.exit_price == pytest.approx(102.15)
    assert result.net_price_move == pytest.approx(-2.3)


def test_walk_forward_split_is_time_ordered():
    from research.walk_forward import split_walk_forward

    idx = pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")
    df = pd.DataFrame({"time": idx, "x": range(10)})
    parts = split_walk_forward(df, train=0.6, validation=0.2)
    assert parts.train["x"].tolist() == list(range(6))
    assert parts.validation["x"].tolist() == [6, 7]
    assert parts.test["x"].tolist() == [8, 9]
