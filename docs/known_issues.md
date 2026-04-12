# Known Issues

## Fixed: Multi-Asset Portfolio Accounting Inflation

- Bug:
  - paper cash and `portfolio_value` could explode to impossible values during multi-asset operation
- Root cause:
  - execution sizing and valuation reused cached `market_value` fields as if they were canonical portfolio truth
  - sequential multi-asset fills could compound stale or derived values instead of rebuilding equity from cash plus per-symbol quantity
  - legacy single-asset ledger fields made the drift harder to inspect in a multi-asset context
- Fixed behavior:
  - cash changes only from executed notionals and proceeds
  - position quantity and average entry update per symbol
  - `portfolio_value` is rebuilt from `cash_usd + sum(position_qty * latest_price)`
  - invariant violations now raise immediately

## Critical Invariant

- `portfolio_value = cash_usd + sum(position_qty[symbol] * latest_price[symbol])`

Any future mismatch between persisted equity and this formula should be treated as a critical accounting bug.
