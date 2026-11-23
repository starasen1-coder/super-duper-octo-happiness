import pandas as pd
from research.features import liquidity_pool_high, liquidity_pool_low, sweep_high, sweep_low

def test_liquidity_levels_use_only_previous_bars():
    df = pd.DataFrame({
        "open":[1,2,3,4,5],
        "high":[2,3,4,10,6],
        "low":[0,1,2,3,4],
        "close":[1,2,3,4,5],
    })
    h = liquidity_pool_high(df, 2)
    assert pd.isna(h.iloc[0])
    assert h.iloc[2] == 3
    assert h.iloc[3] == 4

def test_sweep_is_close_back():
    df = pd.DataFrame({
        "open":[1,2,3,4,5],
        "high":[2,3,4,5,10],
        "low":[0,1,2,3,4],
        "close":[1,2,3,4,4],
    })
    assert bool(sweep_high(df, 2).iloc[4])
    assert not bool(sweep_low(df, 2).iloc[4])
