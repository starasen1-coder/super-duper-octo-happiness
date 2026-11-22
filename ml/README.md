# XAUUSD ML edge filter

This package adds a small, reproducible PyTorch research layer to the MT5
project.

## What is taken from the TopDeepLearning review

The referenced TopDeepLearning list highlights mature PyTorch/TensorFlow
ecosystems and time-series/deep-learning projects. For this repository we use
the useful ideas, not copied repository code:

- PyTorch for a small sequence model.
- LSTM/sequence modeling for ordered market observations.
- Chronological validation instead of random train/test shuffling.
- Checkpointing and reproducible seeds.
- A probability filter rather than letting the neural network invent trades.

The original TopDeepLearning repository is a catalog, not a trading strategy.
Its current list includes PyTorch, TensorFlow and TradingAgents among many other
projects.

## Intended data flow

MT5 / historical CSV
-> feature engineering
-> deterministic liquidity + structure candidate
-> sequence model
-> P(setup reaches favorable move before adverse move)
-> trade / reject

The model should not receive future prices or future-derived indicators.

## Features

Keep the feature set explicitly non-MA. Recommended inputs for the first
experiment:

- OHLC returns/ranges
- tick volume and relative volume
- distance to H1 liquidity levels
- sweep direction and sweep size
- BOS/CHoCH state
- impulse range/body ratio
- ATR-normalized movement
- distance to H1/M15 value-area boundaries
- session
- spread/cost estimate

The target should be defined from future path, for example:

1 = after a valid candidate, price reaches +TP before -SL within H bars

0 = otherwise

Do not train on the trade result alone if the result definition changes between
experiments.

## Critical validation rule

Use expanding walk-forward folds. Do not randomly shuffle market rows.
Keep an embargo around the split when the target uses a multi-bar future
window.

The supplied walk_forward.py provides the fold generator and basic binary
classification metrics.

## First experiment

Use the existing deterministic XAUUSD liquidity-retest candidate generator.
Train the LSTM only on historical candidates. Compare:

1. deterministic strategy without ML;
2. deterministic strategy + ML probability threshold;
3. ML-only benchmark (research only, not the deployment strategy).

The key result is out-of-sample expectancy after spread/commission/slippage,
not accuracy alone.


## Offline OHLCV research harness

Run from the repository root:

```bash
pip install -r requirements-ml.txt
python -m unittest discover -s tests -v
python -m ml.research --csv path/to/XAUUSD_M5.csv --out research_output --horizon 48 --rr 2.0 --cost-r 0.10
```

Accepted time columns: `time`, `datetime`, `date`, `timestamp`. OHLC columns are required; `Tick Volume` / `volume` is optional. `--cost-r` is round-trip cost in R units. The CSV spread column is not converted to price because broker point size and digits differ.

The current harness is an initial, explicit benchmark: 36-bar sweep/reclaim + impulse, next-bar-open entry, stop beyond sweep wick, fixed-R target, and conservative stop-first handling when TP and SL are touched in the same candle. It is **not yet an exact reproduction** of the MT5 EA: H1 BOS/CHoCH, OB retest, Volume Profile, news/session filters and broker-specific execution are not included. Do not compare its output to live EA results as if they were the same rules.

Optional `predictions.csv` must contain out-of-fold `event_index,probability`. The harness compares the ML-filtered subset with the exact same matched candidate set before filtering. In-sample predictions are not evidence of an edge.

No XAUUSD historical dataset was present in the repository during implementation. Synthetic unit tests validate mechanics only; they do not establish profitability or superiority.


## Two-sided XAUUSD M5 history and spread

Primary source: Dukascopy public historical feed, accessed through the open-source
`dukascopy-node` downloader. Dukascopy lists XAUUSD M5 availability from
2003-05-05 UTC. The CLI supports separate Bid/Ask OHLC downloads, CSV, volume,
and date-range selection. Source documentation:
- https://www.dukascopy-node.app/instrument/xauusd
- https://www.dukascopy-node.app/config/cli

Download 2015–2025 (11 calendar years) from the repository root:

```bash
npm --version
python -m pip install -r requirements-ml.txt
python -m ml.download_dukascopy --from-year 2015 --to-year 2025 --output data/XAUUSD_M5_BID_ASK_2015_2025.csv
python -m ml.validate_market_data --csv data/XAUUSD_M5_BID_ASK_2015_2025.csv --json data/XAUUSD_M5_quality.json
python -m unittest discover -s tests -v
```

The downloader invokes `npx dukascopy-node`, so Node.js/npm must be installed
and internet access must be available. It downloads Bid and Ask separately,
matches identical M5 timestamps, and saves both quote sides. It reports
`spread_open = ask_open - bid_open` and `spread_close = ask_close - bid_close`
in **USD price units**, not points. Ask/Bid OHLC extremes are not synchronized
tick-by-tick; therefore open spread is a bar-open estimate and OHLC-derived
mean spread is only a proxy. For exact intrabar spread distributions, use
Dukascopy tick data and aggregate the timestamp-aligned Ask/Bid quotes.

The research loader treats Bid candles as the signal chart. With both quote
sides present, long entries are modeled at Ask open and long exits against Bid;
short entries are at Bid open and short exits against Ask. This avoids the
unrealistic assumption that every trade can enter and exit at Bid. Commission,
slippage and broker-specific execution costs remain separate inputs.

**Important:** Dukascopy is not the user's AMarkets feed. Its spread history
must not be presented as AMarkets historical spread. Use it as an external
reference dataset; obtain a broker-exported tick or M5 Bid/Ask history to
validate the final EA against the intended broker. Do not replace missing
spread with a constant without marking that scenario as synthetic.

Raw market data is intentionally not committed to GitHub: the user downloads
it locally with the script. This keeps the source repository small and preserves
source attribution.
