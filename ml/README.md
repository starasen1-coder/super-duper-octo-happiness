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
