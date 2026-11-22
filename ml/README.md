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
