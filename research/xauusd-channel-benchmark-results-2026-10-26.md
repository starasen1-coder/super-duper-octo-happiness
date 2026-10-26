# XAUUSD channel/momentum benchmark — result (2026-10-26)

## Verdict

**Reject this benchmark. It does not show a positive mathematical edge on the tested historical sample. Do not optimize parameters on the same dataset to force a positive result.**

This was a fixed-rule, price-only benchmark created to compare with the SMC strategy—not an SMC implementation, and not a profitable-robot claim.

## Data and execution

- Source: public monthly XAUUSD M1 Bid/Ask OHLC repository: https://github.com/3650326613-png/dukascopy_xauusd_1m_data
- Matched period: 2015-01-01 00:00 UTC to 2026-08-20 23:58 UTC.
- Inner-joined M1 observations: 6,101,693; complete M5 bars: 1,220,333; H4 buckets with at least 180 minutes: 25,421.
- Median quoted close spread in this dataset: USD 0.40; 95th percentile: USD 1.86.
- Entry: first M1 open at the completed M5 signal close timestamp.
- Long entry/exit: Ask/Bid. Short entry/exit: Bid/Ask.
- In a one-minute bar where SL and TP are both touched, the simulator assumes stop first.
- Scenario A includes the observed Bid/Ask spread, but no extra slippage. Scenario B adds adverse USD 0.05 slippage on each side.
- Broker-specific commission, swap, contract size and margin constraints are not modelled. The simulated equity index assumes 0.5% risk per trade; it is not an MT5 account result.

## Fixed rules (no moving averages)

1. H4 direction: close breaks the previous 20 completed H4-bar channel; direction persists until an opposite breakout.
2. M5 entry: close breaks the previous 12-bar M5 channel in that H4 direction, true range is at least 0.8 × the 14-bar simple ATR, and the candle closes in its outer quarter.
3. Stop: 1.5 × M5 ATR. Target: 2R. One position maximum. No breakeven or trailing stop, so entry quality is tested separately from stop management.

## Aggregate results

| Metric | Scenario A: Bid/Ask only | Scenario B: +$0.05 slippage/side |
|---|---:|---:|
| Closed trades | 22,846 | 23,175 |
| Win rate | 22.48% | 21.00% |
| Average winner | +2.000R | +1.966R |
| Average loser | -1.091R | -1.164R |
| Break-even win rate at these average payoffs | 35.29% | 37.19% |
| Expectancy per trade | **-0.3958R** | **-0.5064R** |
| Sum of per-trade R | -9,043.25R | -11,736.73R |
| Profit Factor (R) | **0.5318** | **0.4491** |
| Longest losing streak | 40 | 54 |
| Simulated 0.5%-risk compounded equity index | fell to zero | fell to zero |

The modelled equity index reaching zero is a mathematical result of compounding this strongly negative expectancy; it is **not** a broker-accurate account or margin simulation. The R-sum is normalized per trade and is not account-currency profit.

### Scenario A by exit year

| Exit year | Trades | Net R | Expectancy R/trade | Profit Factor | Win rate |
|---|---:|---:|---:|---:|---:|
| 2015 | 1,886 | -956.19 | -0.5070 | 0.4356 | 19.57% |
| 2016 | 2,038 | -946.95 | -0.4647 | 0.4748 | 21.00% |
| 2017 | 1,947 | -954.26 | -0.4901 | 0.4542 | 20.39% |
| 2018 | 2,046 | -960.94 | -0.4697 | 0.4658 | 20.48% |
| 2019 | 2,105 | -1,081.58 | -0.5138 | 0.4282 | 19.24% |
| 2020 | 1,868 | -793.37 | -0.4247 | 0.4989 | 21.15% |
| 2021 | 1,974 | -771.92 | -0.3910 | 0.5344 | 22.44% |
| 2022 | 1,927 | -704.02 | -0.3654 | 0.5561 | 22.89% |
| 2023 | 1,936 | -747.46 | -0.3861 | 0.5446 | 23.09% |
| 2024 | 1,907 | -471.18 | -0.2471 | 0.6802 | 26.27% |
| 2025 | 1,990 | -512.04 | -0.2573 | 0.6718 | 26.33% |
| 2026* | 1,222 | -143.34 | -0.1173 | 0.8366 | 30.03% |

*2026 ends on 20 August and is a partial calendar year. Every year in the table is negative; even the best partial year has PF below 1 and negative expectancy.

Both directions failed: scenario A average result was -0.3795R per BUY and -0.4156R per SELL. This is not solved by simply disabling one side.

## What this tells us

- The simple H4-channel/M5-breakout idea is rejected on this dataset.
- The 2R target itself is not enough: the observed win rate is far below the 35.29% break-even rate implied by this strategy's average payoff.
- The negative result persists in each calendar year, so it is not explained by one isolated losing year.
- Quoted spread is material relative to the typical initial stop: median stop distance was about USD 1.36, while the dataset's median close spread was USD 0.40. These are separate distributions, so this comparison is a warning, not a per-trade spread/stop calculation.
- The data is from a public Dukascopy mirror, not AMarkets. Its bid/ask history is more informative than a bid-only candle backtest, but it does not reproduce AMarkets' exact fills, commissions, swaps, margin and symbol contract specifications.

## Next stage: diagnose SMC rather than optimize this failed benchmark

1. Keep this benchmark frozen as a rejected comparator.
2. Re-run the actual SMC candidate in MT5 Strategy Tester using deposit-currency accounting, real ticks where available, and the exact account/symbol cost settings. Export the summary, deal ledger, tester parameters and compiler output from the same run.
3. Use v1.10's setup-funnel counters to record how many M5 bars pass H4 bias, H1 BOS, sweep, displacement/BOS, OB, retest and execution checks. This is diagnostic evidence, not an edge by itself.
4. With the same entry signals, compare fixed 2R exits, breakeven-only and ATR trailing separately. Do not change the entry and exit rules together.
5. Treat the already-inspected 2015–2026 sample as exploratory, not a pristine holdout. Freeze rules before a future evaluation period.

Do not use this benchmark on a live account. The current evidence supports rejecting it, not increasing risk.
