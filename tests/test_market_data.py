import gzip
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ml.download_evtradelabs import download_year
from ml.validate_market_data import validate


def sample_bars():
    return [
        {"ts": 1735686000, "o": 2600.0, "h": 2601.0, "l": 2599.0, "c": 2600.5,
         "ao": 2600.2, "ah": 2601.2, "al": 2599.2, "ac": 2600.7, "v": 100},
        {"ts": 1735686300, "o": 2600.5, "h": 2602.0, "l": 2600.0, "c": 2601.5,
         "ao": 2600.7, "ah": 2602.2, "al": 2600.2, "ac": 2601.7, "v": 120},
        {"ts": 1735686600, "o": 2601.5, "h": 2603.0, "l": 2601.0, "c": 2602.5,
         "ao": 2601.7, "ah": 2603.2, "al": 2601.2, "ac": 2602.7, "v": 130},
    ]


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
            path = Path(tmp) / "bars.csv"
            d.to_csv(path, index=False)
            result = validate(path)
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
            path = Path(tmp) / "bars.csv"
            d.to_csv(path, index=False)
            result = validate(path)
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
            path = Path(tmp) / "bars.csv"
            d.to_csv(path, index=False)
            result = validate(path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["negative_spread_rows"], 1)

    def test_converter_reads_gzip_and_creates_bid_ask_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "source.json.gz"
            with gzip.open(archive, "wt", encoding="utf-8") as stream:
                json.dump(sample_bars(), stream)
            output = root / "bars.csv"
            # Patch network access by passing a file URL through a tiny local HTTP server.
            from http.server import BaseHTTPRequestHandler, HTTPServer
            import threading

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    payload = archive.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                def log_message(self, *_):
                    pass

            server = HTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = download_year(2025, output, f"http://127.0.0.1:{server.server_port}/data")
            finally:
                server.shutdown()
                thread.join()
            self.assertEqual(len(result), 3)
            self.assertAlmostEqual(result.loc[0, "spread_open"], .2)
            self.assertTrue(output.exists())
            checked = validate(output)
            self.assertEqual(checked["verdict"], "PASS")


    def test_short_sunday_session_gap_is_not_hidden_as_weekend(self):
        d = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-07T23:00:00Z", "2024-01-07T23:20:00Z"]),
            "bid_open": [2000.0, 2001.0], "bid_high": [2001.0, 2002.0],
            "bid_low": [1999.0, 2000.0], "bid_close": [2000.5, 2001.5],
            "ask_open": [2000.2, 2001.2], "ask_high": [2001.2, 2002.2],
            "ask_low": [1999.2, 2000.2], "ask_close": [2000.7, 2001.7],
            "spread_open": [.2, .2], "spread_close": [.2, .2],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            d.to_csv(path, index=False)
            result = validate(path)
        self.assertEqual(result["gap_classification_counts"]["intraday_candidate"], 1)
        self.assertEqual(result["intraday_candidate_missing_slots_estimate"], 3)
        self.assertEqual(result["gap_review"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
