# SMC Structure / Liquidity / Impulse v1 — report and source audit

Audit date: 2026-10-26  
EA: `SMC_Structure_Liquidity_Impulse_PRO_v1`  
Instrument/timeframe: XAUUSD M5  
Reported interval: 2024-01-01 to 2026-09-01  
Initial balance: 10,000

## 1. Result from the attached MT5 HTML report

The report labels the account calculation mode as `profit in pips`. Its results must therefore not be interpreted as a validated deposit-currency return. The MetaTrader tester documentation says that pip-profit mode removes commissions and swaps from the calculation and does not perform margin control. This report also shows 0.00 commissions and swaps. A monetary-mode test with realistic costs is required before assessing whether the strategy survives execution.

Values transcribed from the report:
- Net result shown: -1.64
- Gross profit: +827.76
- Gross loss: -829.40
- Profit factor: 1.00 (gross profit / absolute gross loss is about 0.998)
- Total trades: 31
- Winners: 13 (41.94%); losers: 18 (58.06%)
- Average winner: +63.67; average loser: -46.08
- Maximum equity drawdown reported: 4.84%
- Commission/swap: 0.00 / 0.00

These are report units, not a claim about realized money profits.

### Exit attribution

Re-parsing the 31 entry/exit pairs in the report:
- 8 exits labelled TP: all profitable, sum +757.20.
- 23 exits labelled SL: combined sum -758.84. Five of these SL-labelled exits ended at a small profit or near break-even, indicating that break-even/trailing modified the stop before exit.
- Net of the listed exits: -1.64.

The exit labels alone do not prove a bad entry or a bad trailing algorithm. We need an ablation test which keeps entries constant and compares exits, using the same fills and realistic costs.

### Year-by-year result in report units

| Exit year | Closed trades | Sum of reported exit P/L | Winning exits |
|---|---:|---:|---:|
| 2024 | 10 | +235.73 | 6 |
| 2025 | 13 | -143.64 | 4 |
| 2026 (Jan–Aug) | 8 | -93.73 | 3 |
| Total | 31 | -1.64 | 13 |

This split suggests regime sensitivity but cannot establish a persistent regime effect: each year contains only 8–13 trades. Do not optimize on this yearly breakdown as though it were a large independent sample.

### What 31 trades can and cannot prove

The observed win rate is 13/31 = 41.94%. Using a Wilson binomial interval as a rough diagnostic gives approximately 26.4%–59.2% for the underlying win probability. This interval assumes independent Bernoulli outcomes, which trading results may violate, so it is not a full trading-performance confidence interval. It does show how little precision a sample of 31 trades supplies.

The break-even win rate implied by the reported average win and loss is:
`46.08 / (63.67 + 46.08) ≈ 41.99%`.
Observed 41.94% is effectively break-even before costs. The current report does not support a positive edge claim.

## 2. Static source-code audit

These are source-level findings, not claims of a successful MetaEditor compilation.

1. **Risk-lock state resets on EA restart.** `OnInit()` sets `g_initialEquity` and `g_dayStartEquity` from current equity and clears `g_totalDrawdownStop`. Restarting the EA therefore restarts the 10% total-drawdown reference and the daily reference. This weakens the promised protection. Persisted account-level state or a non-resetting external/equity high-water reference is needed before relying on those locks.
2. **H4 bias is a simplified swing heuristic.** `GetH4StructureBias()` compares the two latest confirmed highs and two latest confirmed lows found independently. It does not validate a fully alternating sequence of swing points or measure whether the structure is large enough relative to current volatility. This is not a full market-structure model.
3. **H1 ADX is only one regime proxy.** ADX >= 22 and DI alignment can filter some weak conditions but does not establish that a trend has enough persistence to cover spreads and costs at the eventual M5 entry.
4. **Liquidity sweep is a local mechanical pattern.** The latest swing level is selected and tested for a bounded ATR overshoot and close-back. It does not model equal highs/lows, clustered liquidity, previous-day/session levels, or whether the level is materially relevant.
5. **M5 BOS is a lookback-range break.** The displacement candle must close beyond the maximum/minimum of the preceding lookback, which is an explicit rule but not necessarily a confirmed alternating swing-structure break.
6. **Order Block is a proxy.** `FindOrderBlockZone()` selects the nearest opposite-colour candle in a short lookback. It does not test whether that candle is the actual origin of displacement, whether a fair-value gap aligns with it, or whether the zone has already been materially mitigated.
7. **Stop management and entry should be tested separately.** BE and ATR trailing can convert some losing trades into small winners, but the report shows that total net result remains zeroish. Compare fixed-R exits, BE-only, ATR trailing, and structural target exits against identical entry signals.
8. **Position blocking is symbol-wide.** `HasAnyPositionOnSymbol()` blocks new setups if any position exists on the symbol, regardless of magic number. This is safe against overlap but can cause this EA to stand down because of a manual or another EA's position.
9. **Risk sizing does not reserve trading costs.** `OrderCalcProfit()` estimates stop loss in account currency for the requested price/volume, but the sizing formula does not add a commission/slippage reserve. The attached report has zero commissions/swaps, so its risk profile is not realistic if the broker charges costs.
10. **No compile/test evidence is attached to this report.** Static review is not a substitute for MetaEditor compile output and a monetary-mode Strategy Tester report.

## 3. What the research literature actually supports

- **Moskowitz, Ooi & Pedersen (2012), “Time series momentum”.** Finds 1–12 month return persistence across 58 liquid futures/forwards covering equities, currencies, commodities and bonds. It supports testing a separate momentum benchmark. Its horizon and diversified instruments are very different from XAUUSD M5, so it does not validate this EA. https://doi.org/10.1016/j.jfineco.2011.11.003
- **Szakmary, Shen & Sharma (2010), “Trend-following trading strategies in commodity futures: A re-examination”.** Uses monthly data across 28 commodity markets over 48 years and reports positive net-of-cost mean excess returns for the tested dual-moving-average and channel rules in many markets. That is evidence for testing a simple price-channel benchmark at its relevant horizon, not a promise that intraday CFD trading will work. https://doi.org/10.1016/j.jbankfin.2009.08.004
- **Batten et al. (2018), “Does intraday technical trading have predictive power in precious metal markets?”** Finds no predictability for standard moving-average parameters in its precious-metal intraday tests; a search across many parameter combinations finds some gold configurations, but not silver. The search over parameter combinations itself raises selection risk. https://doi.org/10.1016/j.intfin.2017.06.005
- **Jin (2022), “Performance of intraday technical trading in China’s gold market”.** On five-minute Shanghai gold futures, the paper concludes that apparent predictability did not persist reliably out of sample after accounting for data snooping, costs, market conditions and rebalancing. The market differs from XAUUSD CFD, but this is a direct warning against trusting a single intraday backtest. https://doi.org/10.1016/j.intfin.2021.101481
- **Bailey et al. (2017), “The Probability of Backtest Overfitting”.** Provides a framework to estimate strategy-selection overfitting (CSCV/PBO) and explains why merely reserving one hold-out period may not fully protect an experiment that tries many variants. https://doi.org/10.21314/JCF.2016.322

## 4. Next experiments — no simultaneous parameter fishing

Do not change the live-trading code yet. Treat the current EA as a frozen baseline.

### Experiment 0: make the measurement valid
1. Re-run the exact v1 EA in deposit-currency mode (not `profit in pips`).
2. Select “Every tick based on real ticks” where broker history exists.
3. Set the account deposit and leverage to the intended demo configuration.
4. Include actual account/symbol commission, swap, and realistic spread/execution assumptions. Confirm the report shows costs when applicable.
5. Save the EA file hash, tester settings, full report, deal list and compiler output.

### Experiment 1: simpler, no-moving-average benchmark
The user’s earlier project preference was to avoid MAs in the main signal logic. Use price channels rather than EMA crossings:
- Higher timeframe: direction from a confirmed close breakout of a rolling price range.
- Entry timeframe: pullback/retest or continuation close after that breakout.
- Risk: ATR-normalized stop and position size, fixed R target in the first comparison.
- Regime filter: compare no filter against a predeclared price-based efficiency/range-expansion filter; do not tune a long grid of values.
- One position at a time; no re-entry until a new structural event.

This is a benchmark hypothesis, not a recommended profitable strategy. It must be tested rather than assumed.

### Experiment 2: SMC ablation
Using the same baseline code, change one component per run:
A. H4 structure + H1 BOS/ADX only.  
B. Add M5 sweep.  
C. Add displacement/range break.  
D. Add OB retest.  
E. For the best entry variant only, compare fixed 2R exit, BE at 1R, and ATR trailing.

Record all tested combinations. If a component does not improve out-of-sample net expectancy after cost stress, remove it.

### Validation schedule

The full 2024–2026 period has already been viewed. Do not call it untouched out-of-sample for new tuning. Use it as development/diagnostic data, then lock rules before testing on a genuinely new future interval. If more history can be held back prospectively, use rolling walk-forward folds and report every fold rather than only the best segment.

For each run report:
- Net P/L in deposit currency after costs
- Profit factor and expectancy per trade in R
- Maximum equity drawdown and time under water
- Mean win/loss, payoff ratio and confidence interval
- Number of trades per quarter/year/session and results by volatility/trend regime
- Results with wider spreads/slippage and one-bar-delayed entry
- Compile status and exact tester configuration

## 5. Stop / go criteria

Reject the candidate if:
- net expectancy is non-positive after realistic costs;
- small increases in spread/slippage erase the result;
- results depend on one year or a handful of trades;
- a component helps in-sample but fails in walk-forward folds; or
- the source does not compile cleanly and the run cannot be reproduced.

A modest positive backtest is not yet proof of a durable edge. Do not run this prototype on a live account. The current evidence is insufficient to claim a profitable strategy.
