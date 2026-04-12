# System Architecture

## Portfolio Accounting

- `PortfolioState` is multi-asset and authoritative through `cash_usd` plus `positions[]`.
- Each position is keyed by `symbol` and stores:
  - `quantity`
  - `avg_entry_price`
  - `market_price`
  - `market_value`
  - `unrealized_pnl`
  - `realized_pnl`
- The canonical invariant is:
  - `portfolio_value = cash_usd + sum(position.quantity * position.market_price)`
- `market_value` is derived state for reporting only. It is not a source of truth for sizing or cash accounting.

## Execution And Valuation Flow

- `signal_service` proposes target weights per symbol.
- `risk_service` compares target weight vs current weight and decides `increase`, `reduce`, `flatten`, or `hold`.
- `paper_execution_service` applies the fill to cash and per-symbol quantity:
  - buy: cash decreases by notional, quantity increases, average entry is recomputed from cost basis
  - sell: quantity decreases, cash increases by proceeds, realized pnl is updated from sale price vs average entry
- After every fill, the full portfolio is rebuilt from cash plus per-symbol quantities repriced against the latest known snapshots.
- `trading_loop_service` re-marks the full portfolio to market at cycle end before persisting JSON latest state and SQLite history.

## Multi-Asset Handling

- The engine is portfolio-aware. Weight decisions are per symbol, but valuation is across all held symbols together.
- Current symbol weights are computed from `quantity * market_price`, not from legacy single-asset fields.
- SQLite `positions_json` is the authoritative historical position snapshot for multi-asset state.
- Legacy `btc_qty` and `avg_entry_price` columns remain compatibility fields in the ledger schema; they are not authoritative for portfolio accounting.
- Engine status exposes a portfolio-composition layer for observability:
  - one row per held or selected symbol
  - actual weight from current portfolio valuation
  - target weight from the latest universe/signal context
  - unrealized pnl and market value per symbol
  - explicit cash reserve as a pseudo-position
- Frontend portfolio charts consume that backend composition payload rather than recomputing portfolio shares independently.

## Failure Handling

- Portfolio accounting now fails fast if the invariant is violated.
- The invariant check runs during portfolio rebuild and mark-to-market.
- A violation raises an execution-time error so the cycle is recorded as failed instead of silently creating paper capital.
