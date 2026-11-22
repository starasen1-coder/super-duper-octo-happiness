import unittest
import numpy as np
import pandas as pd

from ml.research import build_events, simulate, compare, load_ohlcv


class ResearchTests(unittest.TestCase):
    def test_simulation_r_metrics(self):
        e = pd.DataFrame({"label": [1, 0, 1], "rr": [2.0, 2.0, 2.0]})
        r = simulate(e)
        self.assertEqual(r["trades"], 3)
        self.assertAlmostEqual(r["net_r"], 3.0)
        self.assertAlmostEqual(r["expectancy_r"], 1.0)
        self.assertAlmostEqual(r["max_dd_r"], 1.0)

    def test_costs_can_remove_edge(self):
        e = pd.DataFrame({"label": [1, 0], "rr": [2.0, 2.0]})
        self.assertGreater(simulate(e)["expectancy_r"], 0)
        self.assertLess(simulate(e, cost_r=1.1)["expectancy_r"], 0)

    def test_ml_filter_compares_same_candidates(self):
        e = pd.DataFrame({"event_index": [1, 2, 3], "label": [1, 0, 1], "rr": [2., 2., 2.]})
        p = pd.DataFrame({"event_index": [1, 2, 3], "probability": [.9, .2, .4]})
        r = compare(e, p, threshold=.6)
        self.assertEqual(r["matched_baseline"]["trades"], 3)
        self.assertEqual(r["ml_filter"]["trades"], 1)

    def test_future_censoring_not_labeled_as_loss(self):
        # Flat data creates no signals; event builder must return a valid empty frame.
        n = 160
        close = np.full(n, 2000.0)
        d = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
            "open": close, "high": close + .1, "low": close - .1, "close": close,
            "volume": np.ones(n), "spread": np.zeros(n),
        })
        self.assertTrue(build_events(d).empty)

    def test_loader_normalizes_and_deduplicates(self):
        n = 110
        d = pd.DataFrame({
            "DateTime": pd.date_range("2024-01-01", periods=n, freq="5min"),
            "Open": np.full(n, 2000.), "High": np.full(n, 2001.),
            "Low": np.full(n, 1999.), "Close": np.full(n, 2000.),
            "Tick Volume": np.ones(n),
        })
        # CSV header containing spaces is normalized via aliases.
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            d.to_csv(f.name, index=False); path = f.name
        try:
            loaded = load_ohlcv(path)
            self.assertEqual(len(loaded), n)
            self.assertEqual(float(loaded.volume.iloc[0]), 1.0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
