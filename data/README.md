# XAUUSD M5 historical data

## Public archive source

EV Trading Labs publishes an annual XAUUSD M5 archive derived from Dukascopy
data. The catalogue documents Bid/Ask OHLC fields and UTC Unix timestamps.
The 2025 archive is publicly accessible without an account:

https://evtradelabs.com/api/simulator/data/XAUUSD/M5/2025.json.gz

Catalogue and licence: https://evtradelabs.com/data
Attribution is required: EV Trading Labs. The catalogue lists the 2025 file as
approximately 2 MB and 70,906 bars. These are source catalogue figures, not
our own post-download validation results.

## Download and convert to CSV

Install Python 3.11 and Node.js 22 LTS (npm is bundled with Node.js). From the
repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-data.txt
node --version
npm --version

npm run data:ev -- --year 2025 --output data\XAUUSD_M5_BID_ASK_2025.csv
npm run data:validate -- --csv data\XAUUSD_M5_BID_ASK_2025.csv --json data\XAUUSD_M5_quality_2025.json
npm run test:python
```

The converter downloads the public gzip JSON archive, converts Unix-second
timestamps to UTC, renames Bid/Ask OHLC columns, and calculates bar-open and
bar-close spread in USD price units. It preserves duplicate/invalid rows so
the validator can detect them.

For 2015–2025, use the separate Dukascopy downloader:
```powershell
npm run data:download -- --from-year 2015 --to-year 2025 --output data\XAUUSD_M5_BID_ASK_2015_2025.csv
```

## What the validator checks

- Missing or invalid timestamps and duplicate candle timestamps.
- Bid and Ask OHLC consistency.
- Negative spread and mismatch between stored spread and Ask minus Bid.
- Gaps greater than five minutes, separated into weekly closures, longer
  session/holiday breaks, and short intraday gaps requiring review.
- Median, 95th percentile and maximum bar-open spread.

Weekend or scheduled market closure is not automatically a data defect.
Short intraday gaps are flagged for review. PASS covers row/quote integrity;
inspect gap_review separately.

## Important limitations

- Archive OHLC bars are not tick-synchronized. Bar-open and bar-close spread
  are estimates; intrabar spread cannot be reconstructed exactly.
- Provider volume is not centralized exchange traded volume.
- This is Dukascopy-derived reference history, not AMarkets broker history.
- Historical quote data does not establish strategy profitability.
- Raw archives and generated CSV files are excluded from Git.
