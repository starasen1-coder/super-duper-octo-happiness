# XAUUSD M5 2025 — data quality report

Source: EV Trading Labs public XAUUSD M5 archive, derived from Dukascopy data.
Catalogue: https://evtradelabs.com/data
Archive: https://evtradelabs.com/api/simulator/data/XAUUSD/M5/2025.json.gz
Attribution: EV Trading Labs.

This report was generated from the downloaded 2025 CSV by
`ml/validate_market_data.py` in GitHub Actions. It is a data-integrity report,
not a strategy backtest.

## Dataset

- Timeframe: M5
- Rows: 70,906
- First timestamp: 2025-01-01 23:00:00 UTC
- Last timestamp: 2025-12-31 21:55:00 UTC
- Exported CSV: `XAUUSD_M5_BID_ASK_2025.csv`
- CSV size: approximately 10.6 MB

## Integrity checks

| Check | Result |
|---|---:|
| Invalid timestamps | 0 |
| Duplicate timestamps | 0 |
| Invalid Bid OHLC rows | 0 |
| Invalid Ask OHLC rows | 0 |
| Negative spread rows | 0 |
| Spread arithmetic mismatches | 0 |

**Quote integrity verdict: PASS.**

## Timestamp gaps

There are 261 intervals longer than five minutes. The validator separates
scheduled market closures from short gaps:

| Classification | Intervals |
|---|---:|
| Weekend / weekly close | 52 |
| Session break / holiday | 205 |
| Short intraday candidates | 4 |

The four short gaps imply six absent M5 timestamp slots. They require source
calendar review; this does not prove that six candles were omitted by a
provider. Exact intervals:

| From UTC | To UTC | Gap | Estimated M5 slots |
|---|---|---:|---:|
| 2025-04-24 22:00 | 2025-04-24 22:10 | 10 min | 1 |
| 2025-08-07 22:55 | 2025-08-07 23:05 | 10 min | 1 |
| 2025-11-28 08:10 | 2025-11-28 08:20 | 10 min | 1 |
| 2025-12-07 23:15 | 2025-12-07 23:35 | 20 min | 3 |

**Gap status: REVIEW.** Inspect these intervals against the provider's trading
calendar before filling or discarding any bars. Do not interpolate synthetic
candles into the original dataset.

## Spread summary

Spread values are in USD price units (Ask minus Bid), not MT5 points:

| Statistic | Bar-open spread |
|---|---:|
| Median | 0.58 |
| 95th percentile | 0.89 |
| Maximum | 14.30 |

Largest bar-open spread observations include:
- 2025-04-24 22:25 UTC: 14.30 USD
- 2025-11-28 09:30 UTC: 12.10 USD

These extreme values should be inspected as potential thin-liquidity, rollover,
holiday, or source anomalies. Do not replace them with a constant spread.

## Limitations

- Bid and Ask OHLC candles are separately aggregated; bar-open/close spread
  estimates are available, but tick-synchronized intrabar spread is not.
- This is a Dukascopy-derived reference feed, not AMarkets broker history.
- The provider's volume field is not centralized exchange traded volume.
- This report does not measure strategy performance or establish an edge.
