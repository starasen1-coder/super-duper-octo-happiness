# Quantitative edge review — 2026-10-26

## Decision

Do not promote the current SMC prototype. The tested configuration does not show a measurable positive edge. Keep it as a benchmark and compare new hypotheses under a locked, reproducible protocol.

## Evidence from the supplied MT5 report

Instrument: XAUUSD, M5. Report interval: 2024-01-01 to 2026-09-01. Initial balance: 10,000.

- Net result: -1.64
- Gross profit: 827.76
- Gross loss: -829.40
- Profit factor: 1.00 (approximately 0.998)
- Trades: 31
- Winners: 13 (41.94%); losers: 18 (58.06%)
- Average winner: 63.67; average loser: -46.08
- Maximum equity drawdown: 4.84%
- Commission and swap columns in the report are zero.

The break-even win rate implied by the rounded average win/loss is:
abs(avg loss) / (avg win + abs(avg loss)) = 46.08 / (63.67 + 46.08) = 41.99%.
Observed win rate is 41.94%, effectively break-even before costs. Wilson 95% interval for 13 wins out of 31 is approximately 26.4%–59.2%; the sample cannot establish a stable win probability.

Important: the report's -1.64 is the net result, not the drawdown. The report itself shows max equity drawdown of 4.84%.

## Code review observations

The EA already combines H4 swing direction, recent H1 BOS + ADX/DI, M5 liquidity sweep, displacement/M5 BOS, and a retest of the nearest opposing candle. That is a complex sequence, but complexity is not evidence of an edge.

1. Only 31 completed trades in roughly 32 months means the sample is too small for confident claims and makes individual exits highly influential.
2. The Order Block definition is a mechanical proxy (nearest opposing candle in a short lookback), not an empirically established predictive signal.
3. Break-even and ATR trailing alter the payoff distribution. They must be tested separately from entry quality; otherwise a poor entry can be mistaken for an exit-management problem or vice versa.
4. The report has no nonzero commissions or swaps. Re-test with realistic broker costs and a cost-stress case.
5. The complete 2024–2026 result has already been inspected; it must not be described as an untouched out-of-sample set for further tuning.

## Research evidence and limits

- Moskowitz, Ooi & Pedersen (2012), “Time series momentum”, Journal of Financial Economics: documents persistence over 1–12 months for a diversified set of 58 liquid futures/forward contracts across asset classes. This supports testing momentum as a separate benchmark; it does **not** prove a profitable XAUUSD M5 SMC strategy. https://doi.org/10.1016/j.jfineco.2011.11.003
- Hurst, Ooi & Pedersen (2017), “A Century of Evidence on Trend-Following Investing”: reports historical evidence for diversified, long-horizon trend following. Again, this is not direct evidence for intraday gold. https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing
- Szakmary, Shen & Sharma (2010), “Trend-following trading strategies in commodity futures: A re-examination”: reports positive net-of-cost results for several long-horizon commodity-futures trend rules across many markets. This is a reason to test a simple breakout/momentum benchmark, not to assume it will work on M5 spot/CFD gold. https://doi.org/10.1016/j.jbankfin.2009.08.004
- “Performance of intraday technical trading in China's gold market” (Journal of International Financial Markets, Institutions & Money, 2022): the study reports that apparent intraday technical-rule predictability on 5-minute Shanghai gold futures was not persistent out of sample after addressing data snooping, costs, market conditions and rebalancing. This is an important counterweight to claims that technical patterns automatically create an edge. https://doi.org/10.1016/j.intfin.2021.101481
- Bailey et al. (2017), “The Probability of Backtest Overfitting”: formalizes the risk of selecting a strategy because it performs well among many tried configurations. https://doi.org/10.21314/JCF.2016.322

## Proposed experiment sequence

Keep the existing SMC EA as the frozen baseline. Do not optimize all filters at once.

### Candidate A — price-momentum / channel breakout baseline
Use a simple, explicit price-based trend hypothesis: a higher-timeframe directional return/close-break filter, an H1 channel breakout or pullback in the same direction, and ATR-normalized risk. Do not use SMC labels unless the exact rules are objectively coded. This candidate is a benchmark to compare with the SMC sequence, not a presumed winner.

### Candidate B — SMC ablation
Run the exact current rules, then remove one component at a time:
- H4 structure + H1 BOS/ADX
- add M5 sweep
- add displacement/M5 BOS
- add OB retest
- separately compare fixed-R exit, break-even, and trailing-stop management

A component earns its place only if it improves out-of-sample net expectancy after costs and does not create unacceptable drawdown. Record all variants attempted.

### Test protocol
1. Use “Every tick based on real ticks” where available; document spread, commission, swap, execution/deviation and account contract specifications.
2. Run development folds and rolling walk-forward tests. Because the full 2024–2026 report has already been viewed, reserve a genuinely unseen future period or otherwise use a pre-registered nested walk-forward protocol; do not retroactively call the inspected period blind out-of-sample.
3. Include adverse execution checks: realistic costs, a wider-spread/cost-stress case, and a delayed-entry case.
4. Report expectancy in R per trade, net profit, profit factor, maximum equity drawdown, average win/loss, number of trades by year/session/regime, and confidence intervals. Compare each candidate with the frozen baseline.
5. Keep a hypothesis log with the reason for each parameter choice and how many trials were attempted. Do not select solely on win rate or the best single backtest.
6. Require all compile errors to be resolved in MetaEditor and keep the EA demo/tester-only until there is evidence from independent validation.

## Stop/go rule

Reject a candidate if its net expectancy is non-positive after realistic costs, if performance collapses under modest cost/slippage stress, or if results depend on one isolated period or a handful of trades. No strategy can be declared profitable from this report; the correct next goal is to falsify weak hypotheses cheaply and preserve only those that survive independent validation.
