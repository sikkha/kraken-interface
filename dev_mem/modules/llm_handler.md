# LLM Handler Module

Location: `library/llm_handler.py`

Purpose:

- Remain the shared, simple entry point for LLM calls:
  - `output = call_LLM(model, prompt)`

Current usage:

- Backend chat service calls this function and converts provider failures into a stable API response for the frontend.
- API keys can now come from direct environment variables or an optional config file path resolved at runtime.
- Docker file-based injection is expected through `/run/secrets/api_key.conf`, typically mounted from repo-local `api_secret/`.

Boundary:

- Keep provider orchestration inside `llm_handler.py`.
- Keep API shaping, fallback messaging, and product-specific prompt wrapping outside the library in backend services.
- Do not turn this file into an application framework.
- Keep secret resolution simple: env vars first, then optional file-based lookup.
