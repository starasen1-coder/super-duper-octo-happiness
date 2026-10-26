import unittest
import numpy as np
import pandas as pd

from xauusd_channel_momentum import (
    aggregate_bars, h4_channel_bias, make_signals, month_range, resolve_exit
)


class TestXAUUSDChannelMomentum(unittest.TestCase):
    def test_month_range_is_inclusive(self):
        self.assertEqual(month_range("2024-11", "2025-02"),
                         ["2024-11", "2024-12", "2025-01", "2025-02"])

    def test_month_range_rejects_reverse_range(self):
        with self.assertRaises(ValueError):
            month_range("2025-02", "2025-01")

    def test_aggregate_bars_drops_partial_buckets(self):
        idx = pd.date_range("2024-01-01", periods=12, freq="min", tz="UTC")
        data = pd.DataFrame(index=idx)
        for side, base in (("bid", 2000.0), ("ask", 2000.2)):
            data[f"{side}_open"] = base + np.arange(12) * 0.01
            data[f"{side}_high"] = data[f"{side}_open"] + 0.10
            data[f"{side}_low"] = data[f"{side}_open"] - 0.10
            data[f"{side}_close"] = data[f"{side}_open"] + 0.02
        out = aggregate_bars(data, "5min", 5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out["minute_count"].tolist(), [5, 5])

    def test_h4_bias_is_available_only_after_completed_bar_close(self):
        idx = pd.date_range("2024-01-01", periods=25, freq="4h", tz="UTC")
        h4 = pd.DataFrame(index=idx)
        h4["bid_high"] = 100.0
        h4["bid_low"] = 90.0
        h4["bid_close"] = 95.0
        h4.loc[idx[20], "bid_close"] = 101.0
        h4.loc[idx[20], "bid_high"] = 101.5
        bias = h4_channel_bias(h4, 20)
        event_time = idx[20] + pd.Timedelta(hours=4)
        self.assertEqual(int(bias.loc[event_time]), 1)
        before = event_time - pd.Timedelta(minutes=1)
        self.assertEqual(int(bias.reindex([before], method="ffill").iloc[0]), 0)

    def test_signal_index_is_bar_close_not_bar_open(self):
        idx = pd.date_range("2024-01-01", periods=40, freq="5min", tz="UTC")
        m5 = pd.DataFrame(index=idx)
        for col, values in {
            "bid_open": [100 + i * 0.1 for i in range(40)],
            "bid_high": [101 + i * 0.1 for i in range(40)],
            "bid_low": [99.8 + i * 0.1 for i in range(40)],
            "bid_close": [100.95 + i * 0.1 for i in range(40)],
            "ask_open": [100.2 + i * 0.1 for i in range(40)],
            "ask_high": [101.2 + i * 0.1 for i in range(40)],
            "ask_low": [100.0 + i * 0.1 for i in range(40)],
            "ask_close": [101.15 + i * 0.1 for i in range(40)],
        }.items():
            m5[col] = values
        close_times = idx + pd.Timedelta(minutes=5)
        bias = pd.Series(1, index=close_times, dtype="int8")
        sig = make_signals(m5, bias, channel_lookback=12, atr_period=14)
        self.assertTrue((sig.index == close_times).all())
        self.assertTrue((sig["signal"].iloc[20:] == 1).any())

    def test_long_ambiguous_bar_assumes_stop_first(self):
        pos = {"direction": 1, "stop": 99.0, "target": 101.0}
        bar = {
            "bid_open": 100.0, "bid_high": 102.0, "bid_low": 98.0,
            "ask_open": 100.2, "ask_high": 102.2, "ask_low": 98.2,
        }
        price, reason = resolve_exit(pos, bar, slippage=0.05)
        self.assertEqual(reason, "sl")
        self.assertAlmostEqual(price, 98.95)

    def test_short_ambiguous_bar_assumes_stop_first(self):
        pos = {"direction": -1, "stop": 101.0, "target": 99.0}
        bar = {
            "bid_open": 100.0, "bid_high": 102.0, "bid_low": 98.0,
            "ask_open": 100.2, "ask_high": 102.2, "ask_low": 98.2,
        }
        price, reason = resolve_exit(pos, bar, slippage=0.05)
        self.assertEqual(reason, "sl")
        self.assertAlmostEqual(price, 101.05)

    def test_long_exit_uses_bid_and_short_exit_uses_ask(self):
        long_pos = {"direction": 1, "stop": 99.0, "target": 101.0}
        bar = {
            "bid_open": 100.0, "bid_high": 100.5, "bid_low": 98.9,
            "ask_open": 100.2, "ask_high": 101.5, "ask_low": 100.1,
        }
        self.assertEqual(resolve_exit(long_pos, bar)[1], "sl")
        short_pos = {"direction": -1, "stop": 101.0, "target": 99.0}
        bar2 = {
            "bid_open": 100.0, "bid_high": 100.5, "bid_low": 98.5,
            "ask_open": 100.2, "ask_high": 101.1, "ask_low": 99.5,
        }
        self.assertEqual(resolve_exit(short_pos, bar2)[1], "sl")


if __name__ == "__main__":
    unittest.main(verbosity=2)
