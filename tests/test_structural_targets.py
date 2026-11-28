import pandas as pd

from research.structural_targets import nearest_confirmed_liquidity_target


def test_long_target_is_nearest_confirmed_high_after_displacement_only():
    bars = pd.DataFrame({
        "open": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
        "high": [101, 101, 101, 102, 102, 101, 103, 102, 101, 100, 120],
        "low": [99] * 11,
    })
    target = nearest_confirmed_liquidity_target(
        bars, entry_index=9, side=1, lookback=20, after_index=4
    )
    assert target == 103.0


def test_short_target_is_nearest_confirmed_low_after_displacement_only():
    bars = pd.DataFrame({
        "open": [100] * 11,
        "high": [101] * 11,
        "low": [99, 99, 99, 98, 98, 99, 97, 98, 99, 100, 80],
    })
    target = nearest_confirmed_liquidity_target(
        bars, entry_index=9, side=-1, lookback=20, after_index=4
    )
    assert target == 97.0


def test_target_is_none_when_no_confirmed_liquidity_exists_beyond_entry():
    bars = pd.DataFrame({
        "open": [100] * 8,
        "high": [101] * 8,
        "low": [99] * 8,
    })
    assert nearest_confirmed_liquidity_target(bars, 7, 1) is None
