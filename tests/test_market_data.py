import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from ml.download_evtradelabs import download_range, download_year
from ml.validate_market_data import validate


def sample_bars():
    return [
        {"ts": 1735689600, "o": 2600.0, "h": 2601.0, "l": 2599.0, "c": 2600.5,
         "ao": 2600.2, "ah": 2601.2, "al": 2599.2, "ac": 2600.7, "v": 100},
        {"ts": 1735689900, "o": 2600.5, "h": 2602.0, "l": 2600.0, "c": 2601.5,
         "ao": 2600.7, "ah": 2602.2, "al": 2600.2, "ac": 2601.7, "v": 120},
        {"ts": 1735690200, "o": 2601.5, "h": 2603.0, "l": 2601.0, "c": 2602.5,
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


    def test_multi_year_download_combines_years_and_preserves_duplicates(self):
        first = pd.DataFrame({
            "timestamp": pd.to_datetime([
                "2015-01-02T00:00:00Z", "2015-01-02T00:00:00Z"
            ]),
            "bid_open": [1200.0, 1200.1],
            "spread_open": [0.3, 0.3],
        })
        second = pd.DataFrame({
            "timestamp": pd.to_datetime(["2016-01-04T00:00:00Z"]),
            "bid_open": [1070.0],
            "spread_open": [0.3],
        })
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "combined.csv"
            with patch("ml.download_evtradelabs.download_year", side_effect=[first, second]) as mocked:
                result = download_range(2015, 2016, output)
            self.assertEqual(mocked.call_count, 2)
            self.assertEqual([call.args[0] for call in mocked.call_args_list], [2015, 2016])
            self.assertEqual(len(result), 3)
            self.assertEqual(int(result.timestamp.duplicated().sum()), 1)
            self.assertTrue(output.exists())
            saved = pd.read_csv(output)
            self.assertEqual(len(saved), 3)

    def test_multi_year_download_rejects_reversed_year_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                download_range(2024, 2015, Path(tmp) / "combined.csv")


    def test_validator_reports_spread_statistics_by_calendar_year(self):
        d = pd.DataFrame({
            "timestamp": pd.to_datetime([
                "2015-01-01T00:00:00Z", "2015-01-01T00:05:00Z",
                "2016-01-01T00:00:00Z", "2016-01-01T00:05:00Z",
            ]),
            "bid_open": [100.0, 100.0, 110.0, 110.0],
            "bid_high": [101.0, 101.0, 111.0, 111.0],
            "bid_low": [99.0, 99.0, 109.0, 109.0],
            "bid_close": [100.5, 100.5, 110.5, 110.5],
            "ask_open": [100.2, 100.4, 110.6, 110.8],
            "ask_high": [101.2, 101.4, 111.6, 111.8],
            "ask_low": [99.2, 99.4, 109.6, 109.8],
            "ask_close": [100.7, 100.9, 110.7, 110.9],
            "spread_open": [.2, .4, .6, .8],
            "spread_close": [.2, .4, .2, .4],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multi_year.csv"
            d.to_csv(path, index=False)
            result = validate(path)
        yearly = {item["year"]: item for item in result["yearly_summary"]}
        self.assertEqual(yearly[2015]["rows"], 2)
        self.assertEqual(yearly[2016]["rows"], 2)
        self.assertAlmostEqual(yearly[2015]["median_open_spread_usd"], .3)
        self.assertAlmostEqual(yearly[2016]["median_open_spread_usd"], .7)


if __name__ == "__main__":
    unittest.main()
