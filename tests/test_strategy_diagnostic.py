import unittest
import pandas as pd

from ml.strategy_diagnostic import detect_sweeps, classify_impulse, simulate


class StrategyDiagnosticTests(unittest.TestCase):
    def test_sweep_requires_close_back_inside_prior_liquidity(self):
        d = pd.DataFrame({
            'high': [10, 11, 12, 11, 10, 10, 10, 10],
            'low': [8, 9, 9, 8, 7, 8, 8, 8],
            'close': [9, 10, 11, 9, 9, 9, 9, 9],
        })
        got = detect_sweeps(d, lookback=4)
        self.assertTrue(bool(got.iloc[4]['long_sweep']))
        self.assertFalse(bool(got.iloc[4]['short_sweep']))

    def test_sweep_rolling_window_does_not_cross_session_gap(self):
        d = pd.DataFrame({
            'high': [10, 11, 12, 11, 10, 10, 10, 10],
            'low': [8, 9, 9, 8, 7, 8, 8, 8],
            'close': [9, 10, 11, 9, 9, 9, 9, 9],
            '_segment': [0, 0, 0, 0, 1, 1, 1, 1],
        })
        got = detect_sweeps(d, lookback=4)
        self.assertFalse(bool(got.iloc[4]['long_sweep']))

    def test_impulse_requires_range_and_body_fraction(self):
        d = pd.DataFrame({
            'open': [10.0, 10.0], 'high': [12.0, 11.0], 'low': [9.0, 9.0],
            'close': [12.0, 10.1], 'atr': [1.0, 1.0],
        })
        got = classify_impulse(d, atr_multiple=1.4, body_fraction=.65)
        self.assertTrue(bool(got.iloc[0]['bull_impulse']))
        self.assertFalse(bool(got.iloc[1]['bull_impulse']))

    def test_stop_wins_when_stop_and_target_are_inside_same_bar(self):
        ix = pd.date_range('2025-01-01', periods=3, freq='5min', tz='UTC')
        d = pd.DataFrame({
            'bid_low': [100, 98, 100], 'bid_high': [101, 103, 103],
            'ask_low': [100.2, 99.9, 100.2], 'ask_high': [101.2, 103.2, 103.2],
            'bid_close': [100.5, 101, 102], 'ask_close': [100.7, 101.2, 102.2],
            'spread_mean_ohlc': [.2, .2, .2],
        }, index=ix)
        sig = pd.DataFrame([{'signal_i': 0, 'direction': 1, 'entry': 100.0, 'stop': 99.0, 'h1_er': .3}])
        trades = simulate(d, sig, rr=2.0, max_wait=2, max_hold=2)
        self.assertEqual(trades.iloc[0]['result'], 'SL')
        self.assertAlmostEqual(trades.iloc[0]['r_multiple'], -1.0)


if __name__ == '__main__':
    unittest.main()
