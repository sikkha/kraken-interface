# Ledger Phase Verification

This note captured the pre-cleanup verification of whether SQLite history and the UI history surfaces were mixing allocator-era rows with the newer dynamic-portfolio-control phase.

Current truth after the cleanup pass:

- `Reset Experiment` now wipes and recreates the SQLite ledger
- new experiments no longer inherit mixed old/new ledger history after reset
- the boundary analysis below remains useful for interpreting historical pre-cleanup data

## Reset and Persistence Truth

At the time of this verification, reset did **not** wipe the SQLite ledger.

- `backend/app/services/engine_service.py`
  - `reset_engine_state()` resets portfolio and engine JSON state
  - deletes selected latest-state JSON files
  - does **not** call any ledger wipe or ledger scoping function
- `backend/app/services/history_ledger.py`
  - only initializes and appends to SQLite
  - exposes list endpoints
  - contains no delete/truncate/reset path
- `backend/app/api/routes/history.py`
  - returns raw recent rows from SQLite with simple `LIMIT`
  - no phase filtering, run scoping, or reset scoping

At that time:

- latest-state JSON = resettable cache
- SQLite ledger = append-only historical store

## Exact Phase Boundary

The old allocator phase and the new dynamic-control phase coexist in the same SQLite file.

Verified boundary:

- old allocator phase: cycles `1` through `106`
- new dynamic-control phase: cycles `107` onward

Evidence:

- cycle `106`
  - `cycle_outcome = risk_rejected`
  - signal rows still show:
    - `target_weight = 0.25`
    - `regime_score = 0.0`
    - empty `action_policy_reason`
  - risk reason still says:
    - `Current paper position is already near the target weight.`
- cycle `107`
  - first signal row with dynamic-policy semantics:
    - `target_weight = 0.0`
    - `regime_score = -0.1368`
    - populated `action_policy_reason`
  - first risk row with new rebalance semantics:
    - `reason = Rebalance gap is inside the configured deadband, so the paper portfolio holds.`
  - engine cycle outcome switched to:
    - `rebalance_not_needed`

Useful timestamps:

- last old cycle finished: `1775659869303` (`cycle_id = 106`)
- first new cycle started: `1775660242612` (`cycle_id = 107`)
- first new cycle finished: `1775660243606` (`cycle_id = 107`)

## Is the Ledger Mixed?

Yes.

Current counts at verification time:

- old cycles: `106`
- new cycles: `18`
- old portfolio snapshots: `106`
- new portfolio snapshots: `18`
- old executions: `106`
- new executions: `18`

Any aggregate query over the full pre-cleanup ledger was mixing allocator-era and dynamic-policy-era behavior unless it filtered to the new boundary.

## Is the UI Mixed?

Partially.

### Recent Cycles panel

Current query path:

- `frontend/src/App.jsx` calls `fetchHistoryCycles(12)`
- backend returns `ORDER BY id DESC LIMIT 12`

At verification time:

- min cycle in the current panel slice: `113`
- max cycle in the current panel slice: `124`

This means the **Recent Cycles panel was phase-clean at that moment**.

### Recent Executions panel

Current query path:

- `frontend/src/App.jsx` calls `fetchHistoryExecutions(12)`
- backend returns `ORDER BY id DESC LIMIT 12`

At verification time:

- min cycle in the current panel slice: `113`
- max cycle in the current panel slice: `124`

This means the **Recent Executions panel was also phase-clean at that moment**.

### Equity Trace

Current query path:

- `frontend/src/App.jsx` calls `fetchHistoryPortfolio(40)`
- backend returns `ORDER BY id DESC LIMIT 40`
- `frontend/src/components/HistoryPanel.jsx` renders all returned portfolio snapshots into the sparkline

At verification time:

- min cycle in current sparkline slice: `85`
- max cycle in current sparkline slice: `124`

That means the **Equity Trace was mixed**. It still included allocator-era rows from cycles `85` to `106`, along with new-phase rows from `107` onward.

## Are Latest-State Cards Safe?

Yes.

The latest signal, risk, execution, portfolio, and engine cards come from JSON latest-state files and engine status, not from aggregated SQLite history. Those cards were safe even while the ledger remained mixed.

## Trustworthy SQL Filters For New-Phase Analysis

Preferred filter:

```sql
WHERE cycle_id >= 107
```

Equivalent cycle filter:

```sql
WHERE id >= 107
```

Timestamp alternative:

```sql
WHERE finished_at_ms >= 1775660243606
```

### New-phase cycles

```sql
SELECT *
FROM engine_cycles
WHERE id >= 107
ORDER BY id DESC;
```

### New-phase signals

```sql
SELECT cycle_id, timestamp_ms, signal, confidence, target_weight, regime_score, exposure_state, action_policy_reason
FROM signals
WHERE cycle_id >= 107
ORDER BY cycle_id DESC;
```

### New-phase risk decisions

```sql
SELECT cycle_id, approved, side, size, target_weight, current_weight, rebalance_gap, exposure_state, action_policy, reason
FROM risk_decisions
WHERE cycle_id >= 107
ORDER BY cycle_id DESC;
```

### New-phase executions

```sql
SELECT cycle_id, status, side, action_policy, target_weight, current_weight_before, current_weight_after, rebalance_gap, reason
FROM executions
WHERE cycle_id >= 107
ORDER BY cycle_id DESC;
```

### New-phase portfolio/equity trace

```sql
SELECT cycle_id, timestamp_ms, cash_usd, btc_qty, portfolio_value, state_source
FROM portfolio_snapshots
WHERE cycle_id >= 107
ORDER BY cycle_id DESC;
```

### New-phase aggregate action counts

```sql
SELECT action_policy, status, COUNT(*) AS count
FROM executions
WHERE cycle_id >= 107
GROUP BY action_policy, status
ORDER BY count DESC;
```

## Safest Next Step

Safest immediate approach:

- keep the ledger append-only
- analyze only filtered new-phase rows using `cycle_id >= 107`

Best structural next improvement:

- add explicit experiment/run/phase IDs to the ledger and optional UI filtering by current experiment phase

Also useful soon:

- add a reset option that can start a new scoped experiment marker without deleting old history
- scope the equity trace to the current experiment phase or to rows after the latest reset
