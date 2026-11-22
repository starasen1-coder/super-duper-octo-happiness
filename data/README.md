# Historical market data

Raw historical data is intentionally kept outside Git so the repository does
not contain large generated datasets.

Download XAUUSD M5 two-sided Bid/Ask bars (default 2015–2025) from the public
Dukascopy historical feed:

```powershell
py -m pip install -r requirements-ml.txt
py -m ml.download_dukascopy --from-year 2015 --to-year 2025 --output data\XAUUSD_M5_BID_ASK_2015_2025.csv
py -m ml.validate_market_data --csv data\XAUUSD_M5_BID_ASK_2015_2025.csv --json data\XAUUSD_M5_quality.json
```

The CSV stores Bid and Ask OHLC, provider volume, and bar-open/bar-close spread
in USD price units. It is not AMarkets broker history. See `ml/README.md`
before using the data in any execution model.
