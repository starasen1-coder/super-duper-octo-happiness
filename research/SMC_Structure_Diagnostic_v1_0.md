# SMC Structure Diagnostic v1.0

## Status
Research prototype committed on branch `research/smc-structure-prototype-2026-10-27`.
This is not a verified profitable strategy. It has not yet been compiled or run in the MetaTrader 5 Strategy Tester in this environment.

## Entry model (no moving averages)
1. **H4 structure bias:** confirmed swing highs/lows; breakout or higher-high/higher-low structure gives bullish bias, lower-high/lower-low gives bearish bias.
2. **M5 liquidity sweep:** the candle at shift 2 must pierce the prior `InpLiquidityLookback` range and close back inside it.
3. **M5 displacement:** the next completed candle (shift 1) must close beyond the sweep candle in the bias direction, have a body of at least `InpMinDisplacementATR × ATR(14)`, and close near its directional extreme.
4. **Execution:** market entry on the first tick of the next M5 bar. Stop goes beyond the sweep extreme plus an ATR buffer; target is a fixed multiple of initial risk.
5. **Risk controls:** risk-percent position sizing via `OrderCalcProfit`, skip if calculated volume is below broker minimum, spread limit, one position per symbol/magic, daily equity-loss entry lockout.

## Deliberate test design
- No moving averages.
- No trailing stop or breakeven in v1.0. Keep exits fixed to isolate entry quality.
- No parameter optimization until the first baseline report is reviewed.
- Chart comment and Journal counters expose the setup funnel: evaluated bars, H4 bias passes, sweep passes, displacement passes, order attempts, accepted orders and rejected orders.

## Known limitations to resolve before relying on results
- The H4 bias is a simple structural classifier, not a complete stateful BOS/CHoCH engine.
- Sweep and displacement are required on consecutive completed M5 candles; this may be too restrictive or may still admit poor setups.
- The daily equity guard resets at the broker's day boundary and is held in memory; it is not persisted across terminal restarts.
- Risk sizing estimates loss from entry to stop; commission, gaps and slippage can make realized loss larger.
- The stop/target are not adjusted after entry. Stop execution can slip.
- The current diagnostic counters are session counters and reset when the EA restarts.

## Required MT5 verification
1. Compile in MetaEditor and save the full compiler output.
2. Test XAUUSD M5 with **Every tick based on real ticks**, account-currency profit calculation (not pips), correct broker commission/swap, deposit and leverage.
3. Export report and deal list. Record net profit, profit factor, expected payoff, max equity drawdown, trades, long/short split, average win/loss, spread and rejected orders.
4. Run separate chronological in-sample and out-of-sample windows. Do not tune parameters to force a positive result on the same sample.
5. Compare the fixed-RR baseline before considering any exit-management changes.
