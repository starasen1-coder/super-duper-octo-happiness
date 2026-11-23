# XAUUSD M5 raw data

The pipeline is designed around public Dukascopy-derived data.

## Source

dukascopy-node can download XAUUSD from 2003 onward as M5 CSV, including bid and ask prices. The research run should use one UTC convention for all sources.

Recommended first dataset:
- XAUUSD M5: 2015-01-01 through 2025-12-31
- bid + ask
- UTC
- CSV
- keep raw files immutable under data/raw/xauusd/

## Download

From the repository root:

    npm install
    npm run data:xauusd:m5

For a smaller smoke test:

    YEARS=2024,2025 npm run data:xauusd:m5

Do not commit downloaded market data to Git unless explicitly required.

## Validation

Normalize the files with research.data_loader. The backtest must account for spread and must not use future bars.
