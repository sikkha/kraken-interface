# Allocator and Storage Verification

This pass verifies current behavior and persistence boundaries without changing trading logic.

## Trading behavior verification

### Verified current theory

The current BTCUSD paper engine is behaving like a capped BTC allocator, not an active trading engine.

Observed recent ledger pattern:

- signals are currently `buy`
- confidence is currently `1.0`
- target weight is currently `0.25`
- the first eligible fill(s) are approved
- later cycles mostly reject with:
  - `Current paper position is already near the target weight.`
- a smaller number reject with:
  - `Cooldown is still active from the last filled trade.`

Recent ledger counts at verification time:

- `Current paper position is already near the target weight.`: 60
- `Signal passed confidence, spread, cooldown, and volatility checks.`: 3
- `Cooldown is still active from the last filled trade.`: 3
- signal tuple `buy / 1.0 / 0.25`: 66 rows

### Why this happens in code

1. `backend/app/services/feature_service.py`
   - builds EMA/MACD-derived rows
   - outputs `lagged_macd`, `lagged_signal`, and `macd_diff`

2. `backend/app/services/signal_service.py`
   - runs packaged GRU inference or fallback proxy
   - computes `confidence_raw` from a trailing mean of predicted MACD
   - computes final confidence with persistence and volatility scaling
   - clamps confidence to `[0.0, 1.0]`
   - maps:
     - positive predicted MACD plus threshold pass -> `buy`
     - target weight = `min(max_position_weight, confidence * max_position_weight)`

3. `backend/app/core/config.py`
   - `MAX_POSITION_WEIGHT` defaults to `0.25`
   - `SIGNAL_CONFIDENCE_THRESHOLD` defaults to `0.18`
   - `TRADE_COOLDOWN_SECONDS` defaults to `3600`

4. `backend/app/services/risk_service.py`
   - rejects `hold`
   - rejects low confidence
   - rejects high spread
   - rejects active cooldown
   - for `buy`, rejects if current paper weight is already near target:
     - `current_weight >= max(size - 0.01, 0)`
   - otherwise approves a buy up to the target weight

5. `backend/app/services/paper_execution_service.py`
   - computes desired notional = `portfolio_value * target_weight`
   - computes trade notional as only the difference between desired and current notional
   - once the portfolio is near 25 percent BTC allocation, later approved buys would naturally shrink toward zero
   - the risk layer usually blocks before that by detecting the portfolio is already near target

### Plain-language summary

The current engine is not actively rotating between buy, hold, and sell in a meaningful way. It currently produces a saturated bullish signal, asks for the same capped allocation every time, fills until the portfolio is roughly 25 percent BTC, and then mostly noops because the risk layer correctly treats the portfolio as already allocated.

## SQLite persistence boundary verification

### Exact paths

- Configured runtime ledger path: `runtime_state/experiment_ledger.sqlite3`
- Backend container working directory: `/workspace`
- Actual ledger path inside backend container:
  - `/workspace/runtime_state/experiment_ledger.sqlite3`
- Actual ledger path on host:
  - `/Users/kan/code/kraken-interface/runtime_state/experiment_ledger.sqlite3`

### Why host and container see the same DB

`compose.yaml` bind-mounts the repo root:

- host: `.` 
- container: `/workspace`

Because the ledger path is relative to the backend working directory, the SQLite file is written into the bind-mounted repo path. That means it is directly visible on the host and persists across normal container restart/rebuild cycles.

### Reset behavior

`POST /api/engine/reset` currently:

- resets portfolio JSON
- deletes latest JSON cache files such as:
  - `latest_execution.json`
  - `latest_market_snapshot.json`
  - `latest_signal.json`
  - `latest_risk_decision.json`
- rewrites engine state JSON

It does **not** delete or truncate `runtime_state/experiment_ledger.sqlite3`.

### Restart and rebuild behavior

Because the DB lives in the bind-mounted repo path, rebuilding or restarting Docker does not remove it unless the host file itself is deleted.

## Suggested next behavioral fixes

Not implemented in this pass, but the next logical changes are:

1. reduce confidence saturation so `1.0` is not the default steady-state output
2. make target weight depend on a more expressive signal policy than `confidence * max_position_weight`
3. add clearer sell / de-risk semantics if the goal is active trading rather than capped allocation
4. keep the current risk layer mostly intact, because it is correctly enforcing the target-allocation contract it is being given

