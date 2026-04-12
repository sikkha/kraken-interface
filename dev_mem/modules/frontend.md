# Frontend Module

Location: `frontend/`

Responsibilities:

- Present the trading workstation shell.
- Show market snapshot data from backend HTTP endpoints.
- Provide an AI assistant panel that talks only to the backend chat route.
- Expose system state and recent backend events for operator visibility.
- Expose operator controls and paper-engine state without bypassing backend contracts.

Current state:

- React + Vite scaffold
- Top status bar
- Market panel now includes a lightweight SVG candlestick chart driven by backend OHLC polling
- Market panel now includes operator controls for time-range presets and switchable candlestick, line, area, and trend chart styles
- Engine control panel now shows paper-engine state, latest signal, latest risk decision, latest execution, and portfolio/pnl summaries
- Frontend now includes a compact history panel fed by SQLite-backed backend history routes
- Frontend can now start, stop, and run the paper engine once through backend routes
- Frontend can now reset the experiment back to configured initial paper capital through the backend reset route
- Operator note text now explains the semantics of run once, start, stop, persistence, and risk-driven noop behavior
- Frontend now includes a persisted dark/light theme toggle in the status bar
- Engine panel metadata now uses cleaner key/value rows and exposes signal artifact status/path more clearly
- Engine panel now also exposes artifact loaded state and runtime note so `gru_packaged` vs fallback is readable at a glance
- Engine panel now also exposes dynamic portfolio-control fields:
  - target weight
  - normalized score
  - policy band
  - current BTC weight
  - rebalance gap
  - exposure state
  - action policy
  - policy reason
- Engine/status surfaces now present the active packaged GRU path explicitly and show fallback as a separate capability rather than as stale notebook wording in the primary engine label
- Engine panel now also renders portfolio observability from backend composition state:
  - actual composition donut with cash
  - per-asset unrealized pnl contribution rows
  - target-vs-actual comparison rows
  - lightweight last-fill reference on open positions when available
- History panel now reflects the richer execution semantics with target weights and action labels instead of only raw side/status text
- History panel now also assumes a hard-reset model:
  - Reset Experiment wipes ledger history
  - equity trace and recent history are expected to start empty after reset
- System status panel
- Event log panel
- AI assistant panel
- Docker image defined in `frontend/Dockerfile`
- Compose service runs the Vite dev server in-container with the repo bind-mounted
- `frontend/node_modules` is isolated in a named Docker volume

Boundary:

- Frontend should not call Kraken directly.
- Frontend should not embed LLM provider logic.
- Frontend should keep talking to backend HTTP routes even when both are containerized.
- Frontend should present signal, risk, execution, and portfolio as separate operator-visible objects rather than collapsing them into one status blob.
- Frontend should make persistence and reset behavior legible rather than assuming the operator knows how `runtime_state/` works.
- Frontend should treat SQLite history as a backend-owned audit surface rather than reading runtime files directly.
- Frontend should keep signal engine identity honest and visible even when it is still falling back to `notebook_proxy`.
- Frontend should make packaged-activation state legible without implying that export tooling is part of the normal operator workflow.
- Frontend should show target/current exposure and action intent clearly enough that the operator can distinguish:
  - signal regime view
  - rebalance decision
  - actual execution outcome
- Frontend should treat reset as a clean experiment boundary and refresh history/equity views accordingly.
