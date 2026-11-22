# XAUUSD ML edge filter

This package contains offline research tools for structured historical data.

## Public XAUUSD M5 archive

A public 2025 XAUUSD M5 archive is available from EV Trading Labs:
https://evtradelabs.com/api/simulator/data/XAUUSD/M5/2025.json.gz

Catalogue: https://evtradelabs.com/data
Attribution: EV Trading Labs. The catalogue reports about 2 MB and 70,906
bars for 2025. These are catalogue figures, not a completed validation result.

Convert the archive to the repository's canonical CSV:

```powershell
python -m pip install -r requirements-data.txt
python -m ml.download_evtradelabs --year 2025 --output data\XAUUSD_M5_BID_ASK_2025.csv
python -m ml.validate_market_data --csv data\XAUUSD_M5_BID_ASK_2025.csv --json data\XAUUSD_M5_quality_2025.json
python -m unittest discover -s tests -v
```

Canonical columns include UTC `timestamp`, Bid/Ask OHLC, `volume`,
`spread_open`, `spread_close` and `spread_mean_ohlc`. Spread is in USD
price units, not MT5 points.

## Data-quality rules

The validator checks invalid timestamps, duplicate timestamps, Bid/Ask OHLC
integrity, negative spreads, quote/spread arithmetic, and timestamp gaps
greater than five minutes. Longer gaps are classified as weekly closures or
session/holiday breaks; shorter gaps are marked as intraday candidates.
Market closures are not automatically counted as missing market data. Review
the generated JSON's `gap_review` and `largest_gaps`.

## Spread limitations

The source contains separately aggregated Bid and Ask OHLC bars. Bar-open and
bar-close spread can be calculated, but intrabar spread distributions cannot
be reconstructed exactly. Timestamp-aligned tick Bid/Ask quotes are required
for exact spread-at-entry/exit analysis. This is Dukascopy-derived reference
history, not AMarkets-specific history.

## ML and strategy research

The LSTM is intended as a filter on deterministic liquidity/structure
candidates, not an autonomous signal generator. Use chronological expanding
walk-forward validation and out-of-fold predictions. Compare the model with
the same matched candidate set and include realistic spread, commission and
slippage assumptions. Do not infer an edge from accuracy or in-sample results.

The current benchmark harness is not an exact reproduction of the MT5 EA:
H1 BOS/CHoCH, OB retest, Volume Profile, news/session filters and
broker-specific execution are not all represented. Data validation does not
prove profitability.
