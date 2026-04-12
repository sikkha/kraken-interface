# Kraken Interface Module

Current reusable root files:

- `client.py` executes the Kraken CLI command.
- `parser.py` normalizes ticker output into a simple snapshot shape.
- `errors.py` defines basic CLI and parsing exceptions.

Current role in scaffold:

- `backend/app/adapters/kraken_market.py` reuses the existing root implementation when live mode is enabled.
- The backend market service now treats the root Kraken CLI proof of concept as the live read path for `/api/market/snapshot`.
- The same backend adapter now also normalizes Kraken OHLC rows into candle objects for `/api/market/candles`.
- Kraken candle reads now feed the backend feature pipeline and signal service for the first BTCUSD paper-loop foundation.
- The operational paper engine now depends on Kraken snapshot and candle reads as the live market input path for each loop cycle.
- Current packaged signal-engine export helper is designed around Kraken BTCUSD candle history rather than the notebook's original `yfinance` universe.
- Frontend time presets currently map into Kraken-compatible interval/limit requests instead of exposing exchange-native controls directly in the UI.
- Docker backend now aims to provide the `kraken` binary inside the image rather than assuming the host shell has already prepared `PATH`.
- Docker live mode should be validated in the running container with `which kraken && kraken --version` plus an actual market read.

Boundary:

- Keep Kraken-specific command execution and response parsing isolated from API routes and frontend code.
- Keep runtime feature construction dependent on normalized candle objects, not on raw CLI payload shapes.
- Future account and execution adapters should follow the same pattern instead of mixing exchange logic into services.
- If the CLI read fails, fallback handling belongs in backend orchestration rather than the frontend.
- Docker CLI availability and successful live reads are separate checks and should be verified explicitly.
