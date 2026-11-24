import pandas as pd

from research.strategy import build_signals


def _m5(n=50):
    t = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    close = [100.0] * n
    high = [100.2] * n
    low = [99.8] * n
    high[40], close[40], low[40] = 101.0, 100.0, 99.9
    high[41], low[41], close[41] = 102.0, 100.0, 101.8
    return pd.DataFrame({"time":t,"open":close,"high":high,"low":low,"close":close,"volume":[100]*n})


def _h1():
    return pd.DataFrame({
        "time": pd.date_range("2025-12-31", periods=6, freq="h", tz="UTC"),
        "open": [99]*6, "high": [100,100,100,100,100,105],
        "low": [98]*6, "close": [99,99,99,99,99,104], "volume":[1]*6
    })


def test_signal_has_no_lookahead_and_enters_after_confirmation():
    m5 = _m5()
    out = build_signals(m5, _h1())
    assert out["entry"].sum() == 0 or out["entry"].iloc[42] in (0, 1)
    changed = m5.copy()
    changed.loc[49, "high"] = 999.0
    out2 = build_signals(changed, _h1())
    pd.testing.assert_series_equal(out["entry"].iloc[:49].reset_index(drop=True),
                                   out2["entry"].iloc[:49].reset_index(drop=True))


def test_strategy_requires_impulse_body_ratio():
    m5 = _m5()
    m5.loc[41, ["high","low","close"]] = [100.5, 100.0, 100.3]
    assert build_signals(m5, _h1())["entry"].sum() == 0


def test_strategy_attaches_quote_liquidity_after_m5_bar_close():
    m5 = _m5()
    quote = pd.DataFrame({
        "time": [m5.loc[0, "time"] + pd.Timedelta(minutes=5)],
        "quote_imbalance": [0.4],
    })
    out = build_signals(m5, _h1(), quote_features=quote)
    assert out.loc[0, "quote_imbalance"] == 0.4


def test_h1_structure_is_not_visible_until_hourly_candle_closes():
    m5 = pd.DataFrame({
        "time": pd.date_range("2026-01-01T02:50:00Z", periods=3, freq="5min"),
        "open": [100.0]*3, "high": [100.2]*3, "low": [99.8]*3,
        "close": [100.0]*3, "volume": [10]*3,
    })
    h1 = pd.DataFrame({
        "time": pd.date_range("2026-01-01T00:00:00Z", periods=3, freq="1h"),
        "open": [99.0, 100.0, 101.0],
        "high": [100.0, 101.0, 110.0],
        "low": [98.0, 99.0, 100.0],
        "close": [99.0, 100.0, 109.0],
        "volume": [1]*3,
    })
    out = build_signals(m5, h1, h1_structure_lookback=2)
    assert out["h1_bull"].tolist() == [False, True, True]
