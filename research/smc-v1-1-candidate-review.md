# SMC v1.10 candidate review — 2026-10-26

This is an implementation candidate, not a verified profitable EA.

## Why this candidate exists
The supplied v1.00 report showed 31 trades, net result -1.64, PF about 0.998 and reported equity drawdown 4.84%; the report also used “profit in pips” with zero commissions and swaps. That result does not establish positive expectancy after realistic costs.

The v1.10 candidate focuses on correctness and diagnostics:
1. Protection state is persisted across DEMO EA restarts.
2. Tester runs are isolated from persistent terminal state.
3. Fresh H1 BOS arms a new setup; active setups are then governed by H4 direction, expiry and structure invalidation.
4. The EA prints the funnel counts from H4 bias through accepted entry.
5. Closing-deal loss cooldown includes deal fees.

## Static verification
Eight Python source-regression tests passed locally:
- balanced delimiters after comments/strings are stripped;
- unique event handlers;
- persistent state load/save;
- tester isolation;
- BOS gate limited to setup creation;
- fee-inclusive cooldown;
- funnel diagnostics;
- key-length bound.

These tests do not compile MQL5 and do not run Strategy Tester.

## Still required
- Compile candidate in MetaEditor.
- Run original v1.00 and candidate v1.10 in MT5 with identical parameters, deposit-currency calculation, real ticks where available and actual broker costs.
- Inspect funnel counts and every deal.
- Test the DEMO protection state across a terminal/EA restart.
- Do not merge into main or claim profitability before these checks.
