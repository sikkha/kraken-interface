from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.engine_service import build_copilot_context
from backend.app.services.event_log import emit_event
from library.llm_handler import call_LLM


def handle_chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    model = request.model or settings.default_llm_model
    prompt = _build_prompt(request)

    emit_event(
        level="INFO",
        component="chat",
        message="AI chat request received.",
        data={"model": model},
    )

    result = call_LLM(model=model, prompt=prompt)

    if isinstance(result, str):
        emit_event(
            level="INFO",
            component="chat",
            message="AI chat request completed.",
            data={"model": model, "status": "success"},
        )
        return ChatResponse(
            ok=True,
            reply=result,
            model=model,
            source="library.llm_handler",
            error=None,
        )

    error_message = "LLM call did not return a text response."
    if isinstance(result, dict):
        error_message = str(result.get("error", {}).get("message", error_message))

    emit_event(
        level="INFO",
        component="chat",
        message="AI chat request returned fallback response.",
        data={"model": model, "status": "fallback"},
    )
    return ChatResponse(
        ok=False,
        reply=(
            "The chat route is wired through library.llm_handler, but no live model "
            "response was available. This is a scaffold-safe fallback so the UI and "
            "backend contract stay usable while API keys or provider routing are configured."
        ),
        model=model,
        source="library.llm_handler:fallback",
        error=error_message,
    )


def _build_prompt(request: ChatRequest) -> str:
    trading_context = build_copilot_context()
    if request.context:
        return f"Context:\n{request.context}\n\n{trading_context}\n\nUser:\n{request.message}"
    return f"{trading_context}\n\nUser:\n{request.message}"
