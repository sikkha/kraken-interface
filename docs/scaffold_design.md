# Trading Workstation Scaffold Design

This scaffold adds the smallest serious product foundation around the existing Kraken CLI market reader and the existing `library/llm_handler.py` entry point.

## Structure

- `backend/` contains a FastAPI service with route, schema, service, config, and adapter boundaries.
- `frontend/` contains a React operator console with a market panel, AI assistant panel, status bar, and event log.
- `dev_mem/` stores concise project memory for future agentic coding passes.
- Root Kraken files remain intact and are reused by the live-compatible market adapter.
- Docker Compose is the standard local runtime boundary for backend and frontend development.

## Boundary decisions

- Market access lives behind `backend/app/adapters/kraken_market.py`.
- Account, execution, and strategy integrations are explicit placeholders, not hidden TODOs inside route code.
- AI chat calls go through `backend/app/services/chat_service.py`, which wraps `library/llm_handler.py` instead of expanding it.
- Lightweight observability is handled through an in-memory event log so the backend can report readiness and recent activity without introducing a database.
- Containerization standardizes execution without moving `dev_mem/`, `library/`, or source code out of the repository.

## Reality vs placeholder

- Real today: FastAPI app shape, React app shell, health/system/market/chat endpoints, typed contracts, event logging, mock market snapshots, live-compatible Kraken market seam, LLM routing through `library/llm_handler.py`, and Docker-first backend/frontend development.
- Placeholder today: Trading execution, account state, strategy integration, rich charting, and verified live Kraken CLI support inside containers.
