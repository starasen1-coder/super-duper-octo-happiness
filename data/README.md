# XAUUSD research data

The pipeline uses Dukascopy-derived public historical quote data. Keep raw files immutable and record the source, date range, timezone and download command.

## M5 candles

Recommended initial sample:
- XAUUSD M5: 2015-01-01 through 2025-12-31
- Bid and Ask candles
- UTC CSV
- Store under `data/raw/xauusd/`

Download from the repository root:

    npm install
    npm run data:xauusd:m5

Smoke test:

    YEARS=2024,2025 npm run data:xauusd:m5

## Tick quotes

Download tick quote updates in yearly chunks:

    npm run data:xauusd:ticks

Smoke test:

    YEARS=2024 npm run data:xauusd:ticks

Dukascopy tick rows contain timestamp, askPrice, bidPrice, askVolume and bidVolume. The quote-side volumes represent volume available at the quoted prices; they are not classified executed trades. Therefore derived bid/ask quote imbalance must be named Quote Liquidity Imbalance, not aggressive trade delta or exchange order flow.

The research aggregator stores mean quoted volumes, mean/median spread, tick count and a normalized quote imbalance for each M5 bucket. These values are feed-specific liquidity observations and must not be interpreted as market-wide positioning.

Do not commit downloaded market data to Git unless explicitly required.
