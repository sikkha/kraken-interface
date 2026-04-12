# System Architecture

High-level flow:

1. Docker Compose starts backend and frontend as the standard local runtime.
2. Frontend calls backend HTTP routes.
3. Backend routes delegate to small services.
4. Market service chooses mock or live Kraken reads behind the same snapshot and candle schemas, while the frontend maps operator presets into candle requests.
5. Engine services can now run those trading-loop services once or on a background interval in paper mode, and can reset experiment state back to configured initial capital.
6. Trading loop services take BTCUSD candles through feature engineering, packaged GRU regime scoring when the artifact is valid, dynamic long/flat portfolio-control policy, risk gating, and paper execution contracts.
7. Services use explicit adapters for exchange or strategy seams.
8. AI chat service wraps `library/llm_handler.py` and now includes lightweight trading-engine context.
9. Event log service records lightweight operational history for inspection.
10. Latest engine and paper-loop state is persisted in lightweight JSON under `runtime_state/`.
11. Each engine cycle now also appends durable SQLite history into `runtime_state/experiment_ledger.sqlite3`.
12. Full experiment reset now wipes and recreates that SQLite file so the next run begins with clean history.

Current layer boundaries:

- Presentation: `frontend/`
- API + orchestration: `backend/app/api` and `backend/app/services`
- Contracts: `backend/app/schemas`
- Exchange seams: `backend/app/adapters`
- Paper loop persistence: `runtime_state/`
- Experiment history ledger: `runtime_state/experiment_ledger.sqlite3`
- Engine lifecycle orchestration: `backend/app/services/engine_service.py`
- Packaged signal runtime: `backend/app/signal_engine/`
- Packaged artifact: `artifacts/signal_engine/btcusd_gru_packaged.json`
- Shared LLM utility: `library/llm_handler.py`
- Project memory: `dev_mem/`
- Runtime orchestration: `compose.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`
- Docker secret mount: `./api_secret` -> `/run/secrets` for backend file-based config injection

Important principle:

- Live exchange access should be pluggable.
- Market reading can mature independently from order execution.
- Strategy outputs should be insertable without forcing a backend rewrite.
- Signal runtime should be able to graduate from `notebook_proxy` to packaged inference without changing downstream risk or execution layers.
- Packaged inference and fallback semantics should remain explicit so operator-facing status is truthful even when export tooling or runtime loading fails.
- Risk approval should remain an explicit step between model signal and any execution path.
- Paper execution should be the proving ground before any real-money execution exists.
- Operator controls should speak to explicit backend engine routes rather than manipulating trading state client-side.
- Experiment persistence and reset behavior should stay explicit in both backend contracts and frontend copy.
- Historical traceability should stay transparent enough for later equity-curve and audit views, but a full operator reset is now treated as a clean experiment boundary rather than a continuation.
- Current Docker persistence boundary is now verified:
  - backend writes the ledger at `/workspace/runtime_state/experiment_ledger.sqlite3`
  - the host sees the same file at `/Users/kan/code/kraken-interface/runtime_state/experiment_ledger.sqlite3`
  - this works because the repo root is bind-mounted into the backend container
- Current algorithm verification now distinguishes two layers clearly:
  - packaged GRU output meaning = predicted current MACD regime state
  - downstream signal policy meaning = dynamic BTC long/flat exposure controller
- Current control architecture is now explicitly rebalance-oriented:
  - signal layer proposes target BTC exposure and exposure state
  - risk layer compares target exposure with current portfolio weight
  - execution layer increases, reduces, flattens, or noops accordingly
  - deadband logic limits micro-churn
- Current execution architecture is now explicitly cash-and-quantity based:
  - position quantity is the canonical per-symbol holding state
  - cash moves only by executed notionals and proceeds
  - equity is recomputed from cash plus per-symbol quantity * latest price after each fill
  - derived `market_value` fields are reporting outputs, not valuation inputs
- Current observability architecture now includes a backend-provided portfolio composition layer:
  - actual weights come from current portfolio valuation
  - target weights come from latest universe/signal context
  - cash is represented explicitly as reserve capital
  - the frontend renders charts from that backend composition payload instead of recomputing portfolio shares independently
- The critical portfolio invariant is now enforced in code:
  - `portfolio_value = cash_usd + sum(position.quantity * position.market_price)`
  - any mismatch is treated as a hard accounting failure for the cycle
- Current policy architecture is now explicitly continuous rather than binary:
  - sufficiently negative regimes still map to flat
  - mildly negative / near-neutral regimes can map to exploratory long exposure
  - stronger positive regimes scale toward the configured max long cap
  - the packaged GRU remains a regime input while the portfolio-control layer owns exposure sizing
- Current UI history architecture is only partially phase-clean:
  - after a full reset, recent cycle/execution lists and the equity trace now start empty because the ledger is recreated
  - later mixed-history support should use explicit experiment/run scoping instead of accidental carry-over
- Current operator portfolio views are latest-state based rather than ledger-aggregate based, so composition and target-vs-actual reflect the current book without phase-mixing.
- Current ledger portfolio snapshots are multi-asset through `positions_json`; legacy BTC-only helper columns are not authoritative in the portfolio architecture.
- Docker should standardize execution while leaving source code, `dev_mem/`, and `library/` as visible repo assets.
- Live Kraken market reads should remain a backend concern with clear fallback behavior rather than leaking source-specific logic into the UI.
- Container behavior should be based on container-local PATH, dependencies, and secrets rather than inherited host shell setup.
