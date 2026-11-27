# Agent instructions

This repository contains an MT5/MQL5 research project. Use the repository as the source of truth.

## Strategy objective
For XAUUSD M5, prioritize a measurable after-cost edge and elimination of systematic entries inside sideways conditions. Do not optimize for trade count or win rate alone.

## Required setup sequence
H1/H4 confirmed structure -> M5 liquidity pool -> liquidity sweep with close back through the level -> confirmed displacement/impulse -> last opposing candle as OB -> OB retest -> entry -> structural SL -> structural liquidity TP.

## Hard rules
- No moving-average dependency in the core SMC logic.
- Never enter merely because an impulse has already happened.
- OB retest is required for execution candidates.
- Flat/range conditions must produce NO TRADE.
- SL must be structurally justified beyond OB/sweep.
- TP must use structural liquidity and require RR >= 2 unless a research test explicitly studies another RR.
- Use closed candles for signal confirmation; do not use future data or repainting logic.
- Record explicit NO TRADE reasons.
- Separate signal generation from execution and from LLM filtering.
- LLM may reject/annotate a deterministic setup; it must not create an entry that bypasses deterministic structure/liquidity rules.

## Verification
Every code change must be statically checked. MQL5 changes must be marked as NOT COMPILED unless MetaEditor/MT5 compilation was actually run. Never claim profitability without an MT5 Strategy Tester report.

## Free-model routing
The preferred LLM transport is an OpenAI-compatible endpoint. For local free-model routing, use FreeLLMAPI/OB-1 according to its current documentation. Keep provider keys out of Git and source files.

## Change discipline
- Prefer a dedicated branch and pull request.
- Keep research/diagnostic tools separate from execution EAs.
- Do not silently replace the existing strategy with an unrelated strategy.
- Preserve reproducibility: log parameters, symbol, timeframe, data window and test assumptions.
