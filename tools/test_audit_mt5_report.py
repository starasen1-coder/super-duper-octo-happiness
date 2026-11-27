import tempfile
import unittest
from pathlib import Path
from audit_mt5_report import audit

HEADER = """<tr><th>Время</th><th>Сделка</th><th>Символ</th><th>Тип</th><th>Направление</th><th>Объем</th><th>Цена</th><th>Ордер</th><th>Комиссия</th><th>Своп</th><th>Прибыль</th><th>Баланс</th><th>Комментарий</th></tr>"""

def make_report(net="-1.64", pnl1="-2.00", pnl2="0.36", final="9998.36", currency="прибыль в пипсах"):
    return f"""<html><body>
    <table><tr><td>Валюта:</td><td>{currency}</td></tr>
    <tr><td>Начальный депозит:</td><td>10 000.00</td></tr>
    <tr><td>Чистая прибыль:</td><td>{net}</td></tr></table>
    <table>{HEADER}
    <tr><td>2024.01.01 00:00:00</td><td>1</td><td></td><td>balance</td><td></td><td></td><td></td><td></td><td>0.00</td><td>0.00</td><td>10 000.00</td><td>10 000.00</td><td></td></tr>
    <tr><td>2024.01.02 00:00:00</td><td>2</td><td>XAUUSD</td><td>buy</td><td>out</td><td>0.1</td><td>2000</td><td>2</td><td>0.00</td><td>0.00</td><td>{pnl1}</td><td>9998.00</td><td>sl 2000</td></tr>
    <tr><td>2025.01.02 00:00:00</td><td>4</td><td>XAUUSD</td><td>sell</td><td>out</td><td>0.1</td><td>1999</td><td>4</td><td>0.00</td><td>0.00</td><td>{pnl2}</td><td>{final}</td><td>tp 1999</td></tr>
    </table></body></html>"""

class TestMT5ReportAudit(unittest.TestCase):
    def run_audit(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.html"
            p.write_bytes(b"\xff\xfe" + text.encode("utf-16le"))
            return audit(p)

    def test_reconciled_deal_ledger(self):
        r = self.run_audit(make_report())
        self.assertAlmostEqual(r["summary_net_profit"], -1.64, places=2)
        self.assertAlmostEqual(r["ledger_pnl_sum"], -1.64, places=2)
        self.assertAlmostEqual(r["final_ledger_balance"], 9998.36, places=2)
        self.assertEqual(r["closed_deals"], 2)
        self.assertTrue(any("profit in pips" in x for x in r["warnings"]))

    def test_net_mismatch_is_reported(self):
        r = self.run_audit(make_report(net="5.00"))
        self.assertTrue(any("!= closing-deal P/L sum" in x for x in r["warnings"]))

    def test_final_balance_mismatch_is_reported(self):
        r = self.run_audit(make_report(final="10001.00"))
        self.assertTrue(any("!= final ledger balance" in x for x in r["warnings"]))

if __name__ == "__main__":
    unittest.main()
