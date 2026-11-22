import tempfile
import unittest
from pathlib import Path
import pandas as pd

from ml.validate_market_data import validate


class MarketDataValidationTests(unittest.TestCase):
    def test_valid_bid_ask_bars_and_spread(self):
        d = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC"),
            "bid_open": [2000.0, 2001.0, 2002.0],
            "bid_high": [2001.0, 2002.0, 2003.0],
            "bid_low": [1999.0, 2000.0, 2001.0],
            "bid_close": [2000.5, 2001.5, 2002.5],
            "ask_open": [2000.2, 2001.2, 2002.2],
            "ask_high": [2001.2, 2002.2, 2003.2],
            "ask_low": [1999.2, 2000.2, 2001.2],
            "ask_close": [2000.7, 2001.7, 2002.7],
            "spread_open": [.2, .2, .2],
            "spread_close": [.2, .2, .2],
        })
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bars.csv"
            d.to_csv(p, index=False)
            result = validate(p)
        self.assertEqual(result["verdict"], "PASS")
        self.assertAlmostEqual(result["median_open_spread_usd"], .2)
        self.assertEqual(result["rows"], 3)

    def test_spread_quote_mismatch_fails(self):
        d = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"),
            "bid_open": [2000.0], "bid_high": [2001.0], "bid_low": [1999.0], "bid_close": [2000.5],
            "ask_open": [2000.2], "ask_high": [2001.2], "ask_low": [1999.2], "ask_close": [2000.7],
            "spread_open": [.5], "spread_close": [.2],
        })
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bars.csv"
            d.to_csv(p, index=False)
            result = validate(p)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["spread_quote_mismatch_rows"], 1)

    def test_negative_spread_fails(self):
        d = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"),
            "bid_open": [2000.0], "bid_high": [2001.0], "bid_low": [1999.0], "bid_close": [2000.5],
            "ask_open": [1999.9], "ask_high": [2000.9], "ask_low": [1998.9], "ask_close": [2000.4],
            "spread_open": [-.1], "spread_close": [-.1],
        })
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bars.csv"
            d.to_csv(p, index=False)
            result = validate(p)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["negative_spread_rows"], 1)


if __name__ == "__main__":
    unittest.main()
