# Operational Paper Engine Milestone

This milestone turns the earlier paper-loop foundation into an operator-facing paper engine that can be started, stopped, run once, and inspected from the workstation.

## Operator semantics

- `Run Once` executes exactly one full paper-engine cycle:
  - market read
  - feature build
  - signal generation
  - risk decision
  - paper execution or noop
  - portfolio and pnl update
  - event emission
  - persistence update
- `Start` begins continuous paper looping at the configured interval and keeps running until `Stop` is used.
- `Stop` prevents future cycles but preserves the current `runtime_state/` files.
- Portfolio state is persistent by default and is resumed from `runtime_state/` unless the operator resets the experiment.
- Risk approval does not guarantee a fill. It only enables the execution step for that cycle. A cycle can still result in `noop`.

## What is operational now

- A background paper loop runner exists in the backend.
- The runner supports:
  - run once
  - start loop
  - stop loop
  - status inspection
- Each cycle performs:
  1. market snapshot and candle read
  2. feature construction
  3. signal generation
  4. risk evaluation
  5. paper execution decision
  6. portfolio and pnl update
  7. event emission
  8. persistent state update
- Frontend controls now expose the paper engine state and latest outputs without changing the workstation layout fundamentally.

## Persistence and reset behavior

- Paper state is file-backed under `runtime_state/`.
- The configured initial paper capital comes from `PAPER_STARTING_CASH_USD` and defaults to `10000`.
- `GET /api/engine/status` now exposes whether the current portfolio is:
  - `initial_default`
  - `persisted_runtime_state`
  - `fresh_reset`
- `POST /api/engine/reset` provides explicit reset behavior for controlled experiments.
- The current frontend uses the combined experiment reset path with `scope=all`, which:
  - stops future cycles
  - resets portfolio state to the configured initial paper capital
  - clears latest signal, risk, execution, and snapshot artifacts
  - resets engine counters and timestamps
  - wipes and recreates the SQLite ledger so the next run starts with empty history
- The SQLite file still lives at `runtime_state/experiment_ledger.sqlite3`, but `Reset Experiment` now recreates it cleanly for a fresh run rather than preserving old rows.

## What remains provisional

- The active live Docker signal engine now runs as `gru_packaged` using `artifacts/signal_engine/btcusd_gru_packaged.json`.
- Export still depends on optional tooling dependencies rather than the normal backend runtime image.
- Real-money execution is still intentionally absent.
- The engine now scans a curated liquid crypto universe and can hold a small selected long/flat portfolio in paper mode.
- The chart surface remains BTCUSD-first in this milestone even though the engine now allocates across multiple selected assets.

## Contracts added

- Engine status contract with:
  - running state
  - paper mode
  - symbol scope
  - interval
  - last cycle timestamps
  - last signal and last execution timestamps
  - last cycle status
  - initial paper capital
  - portfolio source and reset metadata
  - total execution, noop, and risk-rejection counts
  - signal engine labeling
- Engine control routes:
  - `GET /api/engine/status`
  - `POST /api/engine/run-once`
  - `POST /api/engine/start`
  - `POST /api/engine/stop`
  - `POST /api/engine/reset`
- Persistent state files:
  - `runtime_state/engine_state.json`
  - `runtime_state/latest_market_snapshot.json`
  - existing latest signal, risk, execution, and portfolio files

## Observability

- Backend event log now includes:
  - engine start
  - cycle started
  - signal produced
  - risk evaluated
  - execution processed
  - portfolio updated
  - cycle finished or failed
  - engine stopped
- Frontend now surfaces:
  - engine state
  - signal
  - risk decision
  - execution result
  - portfolio and pnl summary
  - active signal engine identity, model version, artifact status, and runtime note
  - fallback engine path identity when packaged inference is unavailable
  - a persisted dark/light theme toggle for operator readability

## Copilot alignment

- Chat prompt construction now includes lightweight structured trading-engine context so the assistant can answer with awareness of:
  - latest signal
  - latest risk decision
  - latest execution
  - current portfolio state
