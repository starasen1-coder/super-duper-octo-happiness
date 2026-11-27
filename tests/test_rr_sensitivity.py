import unittest
import pandas as pd

from ml.rr_sensitivity import metrics


class RRSensitivityTests(unittest.TestCase):
    def test_metrics_for_fixed_reward_risk_results(self):
        frame = pd.DataFrame({"r_multiple": [1.0, -1.0, 1.0, -1.0]})
        got = metrics(frame)
        self.assertEqual(got["trades"], 4)
        self.assertAlmostEqual(got["win_rate"], 0.5)
        self.assertAlmostEqual(got["profit_factor"], 1.0)
        self.assertAlmostEqual(got["expectancy_r"], 0.0)

    def test_empty_metrics(self):
        got = metrics(pd.DataFrame(columns=["r_multiple"]))
        self.assertEqual(got["trades"], 0)
        self.assertIsNone(got["profit_factor"])


if __name__ == "__main__":
    unittest.main()
