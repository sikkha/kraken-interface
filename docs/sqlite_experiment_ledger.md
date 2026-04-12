# SQLite Experiment Ledger

This milestone adds a lightweight SQLite-backed experiment ledger without replacing the current paper engine architecture.

## Purpose

- Keep durable historical records for every paper-engine cycle.
- Preserve latest-state JSON files for current workstation compatibility.
- Make paper experiments auditable, queryable, and easier to demo.

## Storage location

- SQLite file path: `runtime_state/experiment_ledger.sqlite3`
- Latest-state JSON files remain under `runtime_state/` alongside the ledger.

## What gets written per successful cycle

Each successful engine cycle now appends:

1. one `engine_cycles` row
2. one `signals` row per scanned symbol
3. one `risk_decisions` row per selected or currently-held symbol
4. one `executions` row per acted-on symbol
5. one `portfolio_snapshots` row for the full portfolio state

Failed cycles still append an `engine_cycles` row with `cycle_outcome = error` and an error message.

## Current schema

- `engine_cycles`
  - cycle timing
  - symbol scope
  - selected symbols JSON
  - market source actually used
  - signal engine type
  - interval
  - cycle outcome
  - error message
- `signals`
  - symbol
  - side
  - confidence
  - base target weight
  - target weight
  - universe score / category / selection rank
  - model version
  - engine type
  - artifact status
  - serialized feature summary
- `risk_decisions`
  - symbol
  - approval
  - side
  - size
  - reason
  - spread / cooldown / volatility flags when available
- `executions`
  - paper status
  - side
  - size
  - price
  - notional
  - reason
- `portfolio_snapshots`
  - cash
  - legacy BTC quantity / average entry convenience fields
  - serialized positions JSON for multi-asset paper state
  - realized/unrealized pnl
  - portfolio value
  - state source

## API surface

- `GET /api/history/cycles?limit=50`
- `GET /api/history/signals?limit=50`
- `GET /api/history/risk-decisions?limit=50`
- `GET /api/history/executions?limit=50`
- `GET /api/history/portfolio?limit=200`

These routes are read-only and are meant for operator inspection, later UI history panels, and downstream analytics work.

## Reset behavior

- `Reset Experiment` now resets the latest paper-engine state **and** wipes the SQLite ledger for the current experiment.
- The backend immediately recreates the SQLite schema after the wipe so history endpoints remain usable.
- A fresh experiment now starts with:
  - initial paper capital restored
  - empty latest-state artifacts
  - empty SQLite history tables

This makes the equity trace and recent history panel trustworthy for a genuinely clean run.

## What remains provisional

- The active packaged path is currently `gru_packaged`, but the ledger still preserves fallback-related fields so later runs can distinguish packaged inference from any future fallback activation.
- The ledger is now multi-asset aware for paper mode, but it still assumes a small curated universe rather than exchange-wide discovery.
- There is no database server dependency and no migration framework yet.
