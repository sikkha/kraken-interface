# Multi-Asset Universe Selection Milestone

This milestone extends the paper engine from single-asset BTC control into a small multi-asset trading portfolio workflow without changing the operator control model.

## Candidate universe

The engine now scans a curated liquid Kraken-accessible universe of 10 USD pairs:

- `BTCUSD`
- `ETHUSD`
- `SOLUSD`
- `XRPUSD`
- `ADAUSD`
- `DOGEUSD`
- `AVAXUSD`
- `LINKUSD`
- `LTCUSD`
- `DOTUSD`

The list is explicit on purpose for this milestone. It avoids exchange-wide discovery churn and keeps the universe auditable.

## Market characterization metrics

Each cycle computes a lightweight metric set per asset from recent candles:

- `realized_volatility`
  - sample standard deviation of recent returns over the last `48` bars
- `average_dollar_volume`
  - average of `close * volume` over the last `24` bars
- `beta_to_btc`
  - covariance of asset returns with BTC returns divided by BTC return variance over the recent `48` bars
- `trend_quality`
  - recent directional consistency multiplied by capped absolute total return over the last `24` bars
- `regime_alignment_score`
  - normalized version of the packaged GRU regime score

These metrics are then converted into transparent component scores:

- `volatility_score`
  - prefers moderate realized volatility near a practical trading center
- `liquidity_score`
  - relative to the strongest recent dollar-volume name in the current candidate set
- `beta_score`
  - higher positive beta to BTC scores better for this milestone
- `trend_quality_score`
  - higher for cleaner directional behavior

## Universe ranking

The current combined score is:

- `0.35 * regime_alignment_score`
- `0.25 * liquidity_score`
- `0.15 * volatility_score`
- `0.15 * trend_quality_score`
- `0.10 * beta_score`

A small penalty is applied when a symbol falls back to mock data during a live scan.

The engine also attaches a simple category label:

- `core_major`
- `high_beta_momentum`
- `liquid_trending`
- `noisy_speculative`

## Selection logic

- The engine ranks the full candidate set by combined universe score.
- It keeps only the top `2-3` names, with the current cap set by `PORTFOLIO_MAX_SELECTED_ASSETS` and defaulting to `3`.
- Selection is not hardcoded to BTC/ETH/SOL; it is score-driven every cycle.

## Portfolio allocation logic

There are now two layers:

1. per-symbol packaged GRU regime signal
2. portfolio allocator across the selected set

Per-symbol signals still produce a raw `base_target_weight`.

The allocator then:

- converts selected symbols into portfolio weight scores using:
  - `base_target_weight * (0.55 + combined_universe_score)`
- sums those raw scores into a gross portfolio target
- caps gross exposure by `PORTFOLIO_MAX_GROSS_WEIGHT` (default `0.55`)
- normalizes selected symbols jointly under that gross cap
- leaves the remainder as explicit cash reserve

This keeps the portfolio coordinated instead of blindly running the old BTC allocator independently on every asset.

## Execution semantics

- Paper mode only
- Long/flat only
- Per-symbol rebalance decisions still use:
  - target weight
  - current weight
  - deadband
  - cooldown
  - spread guard
  - abnormal-volatility hook
- Held symbols that fall out of the selected set can be reduced or flattened through the same rebalance path

## Ledger behavior

Per successful cycle, the SQLite ledger now writes:

- `1` engine cycle row
- `N` signal rows for the scanned universe
- `M` risk decision rows for selected or held symbols
- `M` execution rows for acted-on symbols
- `1` portfolio snapshot row with serialized positions

This keeps the ledger resettable and trustworthy while making multi-asset runs auditable.

## Current limitations

- Paper only
- Long/flat only
- Candidate universe is curated, not dynamically discovered
- The packaged GRU is still being used as a regime/trend-confirmation input, not a direct multi-asset oracle
- Universe scoring is intentionally simple and explainable rather than optimized
