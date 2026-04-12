# Signal Engine Packaging Milestone

This milestone completes real packaged GRU activation for BTCUSD in the live Docker paper engine, while keeping the runtime honest about where export is still optional tooling rather than part of the normal backend image.

## What changed

- The backend now has a dedicated signal-engine runtime layer under `backend/app/signal_engine/`.
- Runtime can load a packaged GRU artifact from:
  - `artifacts/signal_engine/btcusd_gru_packaged.json`
- If a valid artifact is present, the signal service can execute NumPy-based GRU inference in-process without notebook execution.
- If the artifact is missing, invalid, or fails at runtime, the system falls back explicitly to `notebook_proxy` with a visible runtime note.
- A validated artifact has now been exported in a live Docker environment and the paper engine successfully reports `gru_packaged`.

## Packaging and validation outcome

- No trained GRU artifact was present in the repository at the start of the packaging work.
- The first export attempt exposed a real runtime mismatch:
  - the notebook trained the GRU on independent one-step samples
  - the NumPy runtime was incorrectly carrying hidden state across rows
- That mismatch was fixed by making the packaged runtime respect `sequence_length = 1` semantics.
- The validated export now includes:
  - model architecture metadata
  - feature ordering
  - scaler min/max state
  - weights
  - training metadata
  - a NumPy-vs-PyTorch validation summary
- The artifact was exported in Docker live mode because host-side export still fell back to mock candles in this environment.

## Notebook parity notes

Notebook runtime-relevant assumptions preserved:

- input features:
  - `Lagged_MACD`
  - `Lagged_Signal`
  - `MACD_diff`
- indicator family:
  - EMA12
  - EMA26
  - MACD
  - Signal line
  - rolling volatility with a 20-bar lookback
- GRU architecture shape:
  - input size 3
  - hidden size 50
  - linear head to scalar output

Remaining online/runtime gap:

- The notebook used `ForwardMeanPred`, which depends on forward-looking rolling means over future predictions.
- That is not directly available in an online paper engine.
- The current runtime therefore uses an explicit online approximation:
  - packaged GRU path: trailing mean of predicted MACD
  - notebook proxy path: trailing mean of observed MACD proxy

## Files and runtime structure

- Runtime loader:
  - `backend/app/signal_engine/artifact_loader.py`
- NumPy GRU inference:
  - `backend/app/signal_engine/gru_runtime.py`
- Signal service integration:
  - `backend/app/services/signal_service.py`
- Artifact export helper:
  - `scripts/export_btcusd_gru_artifact.py`
- Optional export dependency set:
  - `backend/requirements-signal-export.txt`
- Artifact directory:
  - `artifacts/signal_engine/`

## Operational meaning

- `engine_type = gru_packaged` means a valid artifact was loaded and used.
- `engine_type = notebook_proxy` means the system is still running the fallback signal path.
- Backend status and the engine panel now expose:
  - signal engine type
  - model version
  - artifact status
  - artifact loaded boolean
  - artifact path
  - runtime note
  - feature summary details used in the latest decision
