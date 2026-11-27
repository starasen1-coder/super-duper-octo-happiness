# SMC v1.10 candidate — risk state and setup lifecycle

## Purpose
Make the prototype's protection state and setup-stage telemetry more reliable, without claiming that the entry model has positive expectancy.

## Changes in the candidate
- Persist starting equity, daily equity baseline, daily key, overall drawdown lock and last-loss timestamp for DEMO runs.
- Namespace terminal global variables by account login, hashed server identifier, magic, symbol and an explicit protection-state version.
- Skip persistent terminal global variables inside Strategy Tester so a run does not inherit a previous run's state.
- Require a fresh H1 BOS to arm a new setup, then evaluate an existing setup under H4-direction agreement, its own expiry and structural invalidation.
- Log stage counters when the EA deinitializes.
- Include `DEAL_FEE` when evaluating the closing-deal P/L for a loss cooldown.

## Safety and non-goals
- Candidate stays restricted to Strategy Tester and DEMO accounts.
- No entry indicators or parameter optimization were added.
- No claim is made about profit, mathematical edge or successful compilation.
- This does not replace the MT5 Strategy Tester or a DEMO restart test.

## Reset behavior
A normal restart must preserve the saved protection state. To intentionally create a new state namespace, increment `InpProtectionStateVersion`. Terminal global variables expire after four weeks of inactivity; the running EA refreshes the state periodically.

## Validation requirements
Run Python static checks, then compile in MetaEditor, then compare original v1.00 and candidate v1.10 under identical tester settings with deposit-currency accounting, realistic commissions/swaps and real ticks where available. Compare expectancy in R, PF, equity DD, trade count and stage funnel counts. Increased trade count is not itself an improvement.
