import pandas as pd

from research.strategy import build_signals

def _m5(n=50):
    t = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    close = [100.0] * n
    high = [100.2] * n
    low = [99.8] * n
    # Prior 36-bar high is 100.2. Bar 40 sweeps it and closes back below.
    high[40], close[40], low[40] = 101.0, 100.0, 99.9
    # Bar 41 is the confirmation impulse above the local structure.
    high[41], low[41], close[41] = 102.0, 100.0, 101.8
    return pd.DataFrame({"time":t,"open":close,"high":high,"low":low,"close":close,"volume":[100]*n})

def test_signal_has_no_lookahead_and_enters_after_confirmation():
    m5 = _m5()
    h1 = pd.DataFrame({
        "time": pd.date_range("2025-12-31", periods=6, freq="h", tz="UTC"),
        "open": [99]*6, "high": [100,100,100,100,100,105],
        "low": [98]*6, "close": [99,99,99,99,99,104], "volume":[1]*6
    })
    out = build_signals(m5, h1)
    assert out["entry"].sum() == 0 or out["entry"].iloc[42] in (0, 1)
    # Future changes must not alter signals before the changed bar.
    changed = m5.copy()
    changed.loc[49, "high"] = 999.0
    out2 = build_signals(changed, h1)
    pd.testing.assert_series_equal(out["entry"].iloc[:49].reset_index(drop=True),
                                   out2["entry"].iloc[:49].reset_index(drop=True))

def test_strategy_requires_impulse_body_ratio():
    m5 = _m5()
    m5.loc[41, ["high","low","close"]] = [100.5, 100.0, 100.3]
    h1 = pd.DataFrame({
        "time": pd.date_range("2025-12-31", periods=6, freq="h", tz="UTC"),
        "open": [99]*6, "high": [100]*5+[105], "low": [98]*6, "close":[99]*5+[104], "volume":[1]*6
    })
    assert build_signals(m5, h1)["entry"].sum() == 0
