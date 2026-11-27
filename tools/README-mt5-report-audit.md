# MT5 report audit utility

This helper uses only Python's standard library to cross-check a Strategy Tester HTML summary against the closing deals and final ledger balance.

## Run

```powershell
python tools/audit_mt5_report.py "C:\path\to\ReportTester.html"
python tools/audit_mt5_report.py "C:\path\to\ReportTester.html" --json
```

## Test

From the repository root:

```powershell
python -m unittest discover -s tools -p "test_*.py" -v
```

It handles UTF-16 MT5 HTML reports and falls back to UTF-8 / Windows-1251. It reports net-profit/deal-ledger mismatches, yearly closing-deal results, zero commission/swap, and the “profit in pips” warning. It does not compile MQL5, run the Strategy Tester, or read values from embedded PNG graphs. Check the chart image manually against the report summary and the deal ledger.
