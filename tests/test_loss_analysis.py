import unittest
import pandas as pd

from ml.analyze_trade_outcomes import _stats, _bucket_table


class LossAnalysisTests(unittest.TestCase):
    def test_profit_factor_and_expectancy(self):
        frame = pd.DataFrame({"r_multiple": [2.0, -1.0, -1.0]})
        got = _stats(frame)
        self.assertEqual(got["trades"], 3)
        self.assertAlmostEqual(got["profit_factor"], 1.0)
        self.assertAlmostEqual(got["expectancy_r"], 0.0)

    def test_bucket_summary_respects_minimum_sample(self):
        frame = pd.DataFrame({
            "r_multiple": [1.0, -1.0, 2.0, -1.0, -1.0],
            "feature": [0.1, 0.2, 0.25, 0.4, 0.5],
        })
        got = _bucket_table(frame, "feature", [0, 0.3, 0.6], min_n=3)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["trades"], 3)


if __name__ == "__main__":
    unittest.main()
