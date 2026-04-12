# Trading Loop Foundation

This milestone extracts the smallest production-worthy runtime path from `trading_strategy_asset/autocoda_cross_asset_vs_spy_multi_horizon.ipynb` without pretending the notebook is already a deployable engine.

## Notebook interpretation

Runtime-relevant pieces:

- Feature vocabulary based on BTC price-derived indicators:
  - EMA12
  - EMA26
  - MACD
  - Signal line
  - MACD diff
  - lagged MACD and lagged signal
  - rolling return volatility
- A GRU model shape that was trained in-notebook on `Lagged_MACD`, `Lagged_Signal`, and `MACD_diff`.
- Confidence logic that boosted positive predictions with persistence and optional volatility scaling.

Research-only pieces for now:

- `yfinance` downloads
- multi-asset universe and SPY-relative comparisons
- in-notebook training loops
- backtest scoreboards and benchmark comparisons

## What was extracted now

- A deterministic BTCUSD feature pipeline built from Kraken candle data instead of notebook market downloads.
- A notebook-derived signal engine that preserves the notebook's feature family and confidence vocabulary.
- A structured signal contract, risk gate contract, paper execution contract, and portfolio contract.
- A file-backed persistence layer for latest signal, latest risk decision, latest paper execution, and latest portfolio state.
- Manual `run-once` orchestration routes so the system can be exercised end to end before adding scheduling.

## Important honesty note

The repository now includes a validated packaged BTCUSD GRU artifact plus scaler state, and the live Docker paper engine can use it directly as `gru_packaged`. The fallback `notebook_proxy` path still remains important because export tooling and artifact loading are still explicit operational steps rather than invisible magic.

That means:

- the production path is no longer trapped in the notebook
- the feature layer and signal contract are real
- the backend can report artifact path, artifact status, and fallback/runtime notes explicitly
- the current signal score is deterministic and inspectable
- the final learned-model runtime can later replace the proxy implementation without changing the downstream risk or paper execution contracts

## Runtime contract flow

1. Kraken candles are fetched through the existing market service.
2. The feature layer converts candles into notebook-aligned momentum and volatility features.
3. The signal service produces a deterministic BTCUSD signal object.
4. The risk gate applies confidence, spread, cooldown, max-size, and abnormal-volatility checks.
5. The paper execution service converts approved decisions into long/flat paper fills.
6. Portfolio and PnL state are persisted in `runtime_state/`.
