# XAUUSD M5 historical data

## Primary public source

Dukascopy publishes historical XAUUSD candles from 2003-05-05 UTC, including
M5 and separate Bid/Ask price series. The downloader in this repository creates
a two-sided CSV for 2015–2025. Source page:
https://www.dukascopy-node.app/instrument/xauusd

The CSV is generated locally because the full 11-year dataset is too large and
changes independently of source code. The raw file is intentionally excluded
from Git by `.gitignore`; the reproducible downloader and validation code are
committed instead.

## Windows 10 setup

Install Python 3.11 and Node.js 22 LTS (npm is bundled with Node.js). Open
PowerShell in the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-data.txt
node --version
npm --version
```

## Download and validate 2015–2025

```powershell
npm run data:download -- --from-year 2015 --to-year 2025 --output data\XAUUSD_M5_BID_ASK_2015_2025.csv
npm run data:validate -- --csv data\XAUUSD_M5_BID_ASK_2015_2025.csv --json data\XAUUSD_M5_quality.json
npm run test:python
```

Equivalent direct Python commands:

```powershell
python -m ml.download_dukascopy --from-year 2015 --to-year 2025 --output data\XAUUSD_M5_BID_ASK_2015_2025.csv
python -m ml.validate_market_data --csv data\XAUUSD_M5_BID_ASK_2015_2025.csv --json data\XAUUSD_M5_quality.json
```

The downloader uses `npx dukascopy-node` to fetch Bid and Ask separately,
matches identical M5 timestamps, and saves both quote sides. The CSV contains
Bid/Ask OHLC, source volume where available, and spread estimates. Spread values
are USD price differences, not MT5 points.

## Interpretation and limitations

- `spread_open = ask_open - bid_open` is a bar-open estimate.
- `spread_close = ask_close - bid_close` is a bar-close estimate.
- `spread_mean_ohlc` is only an OHLC-derived proxy. Ask/Bid candle extrema are
  not synchronized tick-by-tick.
- Exact intrabar spread distribution requires timestamp-aligned tick quotes.
- Dukascopy is not AMarkets. Do not label this dataset as AMarkets historical
  spread or use it as an exact broker execution model.
- Historical quote data is for offline software research. It does not establish
  that any strategy has a positive edge or is suitable for live trading.

No raw data file has been downloaded into this repository by the setup commit.
