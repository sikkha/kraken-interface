# Signal Engine Artifacts

This directory is the intended home for packaged BTCUSD signal artifacts.

Expected runtime file:

- `artifacts/signal_engine/btcusd_gru_packaged.json`

Current reality:

- The runtime can load a packaged GRU artifact from that path.
- No validated artifact is committed yet.
- When the artifact is missing or invalid, the backend falls back to the explicit `notebook_proxy` signal engine.

Expected artifact format:

- JSON format id: `autocoda_gru_v1`
- Feature names:
  - `lagged_macd`
  - `lagged_signal`
  - `macd_diff`
- Includes:
  - scaler min/max arrays
  - GRU layer weights
  - linear head weights
  - model metadata
