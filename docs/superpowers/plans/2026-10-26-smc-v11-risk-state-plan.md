# SMC v1.10 candidate — implementation plan

**Goal:** Preserve DEMO risk protection across EA restarts and provide diagnostics for the multi-stage setup logic.

**Architecture:** A separate MQL5 candidate adds terminal-global-variable state helpers, a setup lifecycle adjustment and funnel counters. Python tests cover static source invariants. MetaEditor and MT5 remain the required runtime checks.

**Files**
- Candidate: `SMC_Structure_Liquidity_Impulse_PRO_v1_1.mq5` (provided as a separate candidate artifact in this conversation).
- Static tests: `tools/test_smc_v11_source.py`.
- Design: `docs/superpowers/specs/2026-10-26-smc-v11-risk-state-design.md`.

## Implemented in candidate
- [x] Persist baseline/lock/day/cooldown state for DEMO.
- [x] Keep Strategy Tester state isolated.
- [x] Add explicit state-version reset.
- [x] Let H1 BOS arm a setup rather than requiring BOS freshness on every M5 bar.
- [x] Add setup funnel counters.
- [x] Include deal fee in loss-cooldown calculation.

## Verification
- [x] Eight Python static regression checks pass.
- [ ] MetaEditor compile with zero errors and warnings.
- [ ] DEMO restart test for total drawdown lock and daily baseline.
- [ ] Same-settings monetary-mode Strategy Tester comparison against v1.00.

## Stop/go rule
Do not merge or use beyond Tester/DEMO until compilation and reproducible same-settings tests are recorded. The code-level change is not evidence of profitability; if net expectancy after realistic costs remains non-positive, keep the model rejected rather than optimizing until a lucky result appears.
