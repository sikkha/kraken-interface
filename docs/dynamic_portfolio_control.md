# Dynamic Portfolio Control Policy

This milestone replaces the old capped-allocation behavior with a dynamic long/flat portfolio-control layer for BTCUSD paper trading.

## What Changed

- The packaged GRU artifact is still treated honestly as a regime / trend-confirmation input, not as a direct execution policy.
- The signal layer now converts packaged GRU output into:
  - a bounded `regime_score`
  - a non-saturating `confidence`
  - a dynamic `target_weight`
  - an operator-readable `exposure_state`
- The risk layer now compares `target_weight` to `current_weight` on every cycle and decides whether the engine should:
  - `increase`
  - `hold`
  - `reduce`
  - `flatten`
- The execution layer now supports partial sell-downs as well as full flattening, instead of only top-up buys or full liquidation on sell.

## Policy Shape

- Long/flat only in this milestone.
- Exposure states:
  - `flat`
  - `light_long`
  - `medium_long`
  - `full_long`
- Rebalancing uses a configurable deadband so the engine does not churn around tiny target changes.
- Cooldown, confidence threshold, and abnormal-volatility gating still matter for exposure increases.
- De-risking is allowed to proceed without being blocked by the increase-side cooldown logic.

## Current Mapping

- Packaged GRU output is interpreted as a bounded regime score rather than a direct allocation.
- `target_weight` is derived from:
  - packaged predicted MACD
  - predicted MACD delta
  - current MACD divergence (`macd_diff`)
  - persistence over the recent feature window
  - a volatility penalty
  - a tanh-calibrated confidence score
- The policy now uses a continuous long/flat ramp instead of a binary flat-or-max gate:
  - `SIGNAL_FLAT_SCORE_THRESHOLD = -0.40`
  - `SIGNAL_BUY_SCORE_THRESHOLD = 0.12`
  - `SIGNAL_FULL_SCORE_THRESHOLD = 0.72`
- Regime scores below the flat threshold still map to `0.0`.
- Scores above that threshold are normalized across the configured range and scaled into a capped long exposure.
- Confidence no longer acts like an all-or-nothing saturating switch in this regime window; it now modulates the continuous exposure ramp.
- The signal panel now also exposes:
  - normalized score
  - policy band
  - target weight
  - exposure state

## Exposure Bands

- `flat`
- `exploratory_long`
- `core_long`
- `conviction_long`

These policy bands are operator-facing labels layered on top of the long/flat exposure ramp. They help explain why the engine wants something like `3.8%` instead of only `0%` or `25%`.

## Rebalance Semantics

- `increase`: target weight is materially above current BTC weight.
- `hold`: gap is inside the deadband.
- `reduce`: target weight remains positive but materially below current BTC weight.
- `flatten`: target weight drops to flat while the portfolio still holds BTC.

These semantics now flow through:

- latest-state JSON under `runtime_state/`
- engine status responses
- SQLite history rows
- frontend engine/history panels

## Verification Notes

Verified in this pass:

- Reset still produces a truly fresh run:
  - latest-state JSON cleared
  - SQLite ledger recreated empty
  - active packaged GRU status preserved truthfully
- Fresh live Docker `run-once` no longer collapses to `0.0` target weight in a mildly bearish regime window.
- Fresh-run packaged GRU cycles now produced:
  - `signal = hold`
  - `confidence ~= 0.245 - 0.248`
  - `regime_score ~= -0.167`
  - `target_weight ~= 0.038 - 0.039`
  - `policy_band = exploratory_long`
- The first clean cycle increased into that exploratory target and later cycles correctly held once the rebalance gap fell inside the deadband.
- Earlier dynamic-control verification still remains true:
  - a seeded live paper position produced a real `flatten`
  - deterministic checks confirmed `increase`, `reduce`, and `flatten` execution paths

## Still True

- BTCUSD only
- paper mode only
- no shorting yet
- packaged GRU still acts as a regime input, not a final standalone trading policy
