import pandas as pd

from research.strategy import build_retest_setups


def _fixture(retest_index: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = 65
    time = pd.date_range("2026-01-01T00:00:00Z", periods=n, freq="5min")
    m5 = pd.DataFrame({
        "time": time,
        "open": [100.0] * n,
        "high": [100.2] * n,
        "low": [99.8] * n,
        "close": [100.0] * n,
        "volume": [100] * n,
    })
    m5.loc[40, ["open", "high", "low", "close"]] = [100.05, 100.1, 99.0, 100.0]
    m5.loc[42, ["open", "high", "low", "close"]] = [100.0, 101.3, 99.9, 101.2]
    m5.loc[retest_index, ["open", "high", "low", "close"]] = [100.05, 100.4, 100.0, 100.3]

    h1 = pd.DataFrame({
        "time": pd.date_range("2026-01-01T00:00:00Z", periods=6, freq="h"),
        "open": [99.0, 99.0, 99.0, 100.0, 100.0, 100.0],
        "high": [100.0, 100.0, 100.0, 103.0, 103.0, 103.0],
        "low": [98.0, 98.0, 98.0, 99.0, 99.0, 99.0],
        "close": [99.0, 99.0, 99.0, 102.0, 102.0, 102.0],
        "volume": [1] * 6,
    })
    return m5, h1


def test_long_setup_requires_sweep_impulse_bos_ob_retest_then_next_bar_entry():
    m5, h1 = _fixture(retest_index=49)
    setups = build_retest_setups(
        m5, h1,
        liquidity_lookback=36,
        structure_lookback=6,
        atr_period=14,
        impulse_window=4,
        retest_window=8,
        h1_structure_lookback=2,
        risk_reward=2.0,
    )
    assert len(setups) == 1
    setup = setups.iloc[0]
    assert setup["side"] == 1
    assert setup["sweep_index"] == 40
    assert setup["impulse_index"] == 42
    assert setup["retest_index"] == 49
    assert setup["entry_index"] == 50
    assert setup["entry_price"] == 100.0
    assert setup["stop_price"] == 99.0
    assert setup["target_price"] == 102.0


def test_h1_break_is_not_used_before_hourly_candle_close():
    m5, h1 = _fixture(retest_index=46)
    setups = build_retest_setups(
        m5, h1,
        liquidity_lookback=36,
        structure_lookback=6,
        atr_period=14,
        impulse_window=4,
        retest_window=8,
        h1_structure_lookback=2,
    )
    assert setups.empty
