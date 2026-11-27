# MQL5 implementation audit — SMC Structure / Liquidity / Impulse PRO v1.00

Date: 2026-10-26

## Scope and limits

Reviewed the current source file `SMC_Structure_Liquidity_Impulse_PRO_v1.mq5` and the supplied MT5 tester report. Context7 was used to consult MQL5 documentation on Strategy Tester modes and trade transaction handling. No MetaEditor/MT5 executable is available in this environment, so this is a static review, not a successful compile or Strategy Tester run.

## Findings

### P1 — Total drawdown lock resets when the EA restarts

`g_initialEquity` and `g_totalDrawdownStop` are process-local globals initialized in `OnInit()`. Restarting/re-attaching the EA resets the equity reference and clears the total drawdown stop. This is consistent with the existing comment, but it is not a durable account-level circuit breaker. If the intention is to enforce a persistent limit, persist the peak/initial equity and lock state with terminal global variables keyed by account, symbol and magic, and provide an explicit operator reset procedure. Do not implement persistence silently without documenting its reset semantics.

### P1 — Position risk is an estimate before execution, not a guaranteed cap

`CalculateRiskVolume()` uses `OrderCalcProfit()` between requested entry and SL, then divides the risk budget by that loss. It does not include commission, slippage, gaps, or the difference between requested and actual fill. The log currently describes this as risk percent, which can be read as a hard maximum. Rename the log to “расчётный риск до издержек” and stress-test costs; keep volume rounding down and never round up to broker minimum.

### P1 — Test report does not include real costs

The provided report has zero commission and zero swap. A PF around 1.00 and net loss near zero cannot support a positive-edge claim, especially when execution costs are omitted. Re-run with the broker's actual symbol specification and commission model, then add a conservative spread/slippage stress case.

### P2 — Strategy has several unverified conjunctive filters

The pipeline requires H4 HH/HL or LH/LL, recent H1 BOS plus ADX/DI direction, M5 sweep, M5 displacement/BOS, and OB retest. Each layer reduces trades; none is proven predictive by source-code correctness. Use a frozen baseline and one-factor-at-a-time ablations. Record every tested variant to avoid selecting a lucky configuration.

### P2 — Current “Order Block” is a mechanical proxy

`FindOrderBlockZone()` picks the nearest opposite-colour candle among a small fixed lookback. It does not establish that the candle is the causal origin of displacement or that its zone remains unmitigated. Keep this definition explicit and test it against alternatives; do not present it as an objectively validated market concept.

### P2 — H1 BOS freshness is rechecked before advancing an existing setup

`ProcessNewM5Bar()` returns and resets the setup when the H1 BOS is no longer fresh, even if the sweep/impulse/retest sequence has already started. This can invalidate otherwise complete lower-timeframe sequences as the H1 window rolls forward. Test a variant where H1 BOS is required to arm the setup, and the stored setup remains valid until its own expiry or structural invalidation. Compare it out of sample; do not assume this change improves expectancy.

### P2 — Cooldown trigger is based on a single closing deal

`OnTradeTransaction()` triggers cooldown on each negative exit deal using profit + swap + commission. It does not aggregate all partial exits for a position and does not include `DEAL_FEE`. If partial exits or fees are relevant to the broker, the pause logic may not match the final net result of the position. Validate against deal history and aggregate by position identifier before treating it as a position-level loss.

### P3 — Broad position guard blocks entries if any position exists on the symbol

`HasAnyPositionOnSymbol()` blocks the EA when any position on the symbol exists, regardless of magic number. This is conservative and may be intentional, but it also means a manual trade or another EA can prevent all signals. Document the rule or add an explicit input to choose “any position on symbol” versus “own magic only”; default should remain conservative unless tested.

## Evidence from supplied report

- 31 trades; 13 winners and 18 losers.
- Net result -1.64; gross profit 827.76; gross loss 829.40.
- Profit factor approximately 1.00.
- Average winner 63.67; average loser 46.08.
- Reported maximum equity drawdown 4.84%.
- Reported commission and swap are zero.

Using rounded average win/loss, the break-even win rate is 46.08 / (63.67 + 46.08) = 41.99%, almost exactly the observed 13 / 31 = 41.94%. This does not show a measurable positive edge. With only 31 trades, the confidence interval around win rate is broad.

## Recommended validation sequence

1. Compile the unchanged baseline in MetaEditor; record build number and all warnings/errors.
2. Re-run on real ticks where available, with the correct XAUUSD contract size, tick value, tick size, stops/freeze levels, commission, swap, spread and slippage assumptions.
3. Freeze the baseline before changing any logic.
4. Run a pre-registered ablation set: (a) existing entry and exits; (b) existing entry with fixed-R exit only; (c) entry without BE/trailing; (d) H1 BOS armed once vs rechecked every M5 bar; (e) simple price-breakout/momentum benchmark.
5. Use walk-forward folds. The already-inspected 2024–2026 report is not an untouched blind holdout. Keep a future or otherwise untouched evaluation segment.
6. Compare net expectancy in R/trade, PF, equity drawdown, cost stress, yearly/session breakdown, trade count and uncertainty intervals. Do not rank by win rate alone.
7. Reject variants whose net expectancy is non-positive after costs or whose result collapses under modest spread/slippage stress.

## Agent availability

No registered remote Codex environment was returned by the environment-list tool on 2026-10-26. Therefore no independent remote agent compile/test was launched. A static audit must not be represented as a compiled or backtested result.
