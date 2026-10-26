# XAUUSD channel/momentum benchmark

This is an exploratory, price-only strategy benchmark. It is not an SMC implementation and it does not claim to be profitable.

## Fixed rules (no moving-average signal)

- Historical input: public monthly Dukascopy XAUUSD M1 bid/ask OHLC files from the repository linked in the report.
- H4 regime: a close breaks above the highest high or below the lowest low of the prior 20 completed H4 bars. Direction persists until an opposite H4 breakout.
- M5 entry: close breaks the prior 12-bar M5 channel in the H4 direction, true range is at least 0.8 × the 14-bar simple ATR, and close is in the top/bottom quarter of the candle.
- Entry: the next M1 bar open at the M5 close timestamp, using ask for BUY and bid for SELL.
- Risk: initial stop at 1.5 × M5 ATR; target at 2R; one open position at a time; no BE/trailing so entries and exits remain separable.
- Exit quotes: bid prices to close longs, ask prices to close shorts. If SL and TP both fall inside an M1 bar, stop is assumed first.
- Two scenarios: actual bid/ask spread alone, and an additional adverse $0.05 price slippage per side.

## Download and run

    python -m pip install pandas numpy
    python -m unittest discover -s research/backtests -p "test_*.py" -v
    python research/backtests/xauusd_channel_momentum.py --start 2015-01 --end 2026-08 --data-dir cache --output-dir out

The script downloads monthly files from the public GitHub dataset and writes research_summary.json plus one trade CSV per cost scenario.

## Interpretation

Results are reported in R, including expectancy, PF, compounded equity-index drawdown at 0.5% modeled risk per trade, and exit-year breakdown. The equity index does not model broker contract size, margin, commissions or swap. This is not an AMarkets execution simulation and is not a pristine holdout because the broader research has already inspected overlapping historical years. A future locked period and an MT5 test with broker-specific costs are still required.
