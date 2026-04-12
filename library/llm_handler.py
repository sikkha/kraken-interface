"""Shared LLM helper with provider-aware routing for BaseZero and BaseOne.

Design goals:
- Keep BaseZero stable (OpenAI / GPT-5.x still works)
- Support BaseOne local backends cleanly (Ollama, OpenAI-compatible endpoints)
- Preserve role-based routing (planner / manager / code_implementor / coder / critic)
- Return either plain text on success or a structured error dict on failure
"""

from __future__ import annotations

import os
from configparser import ConfigParser
from dataclasses import dataclass
from typing import Any, Callable

import requests


# ---------------------------------------------------------------------------
# Role routing
# ---------------------------------------------------------------------------

ROLE_DEFAULTS = {
    "planner": {"provider": "openai", "model": "gpt-5.1"},
    "manager": {"provider": "openai", "model": "gpt-5.1"},
    "code_implementor": {"provider": "ollama", "model": os.getenv("AUTOCODA_OLLAMA_MODEL", "gpt-oss:120b")},
    "coder": {"provider": "openai", "model": "gpt-5.1-codex"},
    "critic": {"provider": "openai", "model": "gpt-5.1"},
}


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("AUTOCODA_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_DEFAULT_MODEL = os.getenv("AUTOCODA_OLLAMA_MODEL", "gpt-oss:120b")

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class ResolvedTarget:
    provider: str
    model: str


class APIKeyManager:
    _keys: dict[str, str | None] | None = None

    @classmethod
    def load_keys(cls) -> dict[str, str | None]:
        if cls._keys is None:
            config = ConfigParser()
            config_file_path = cls._resolve_config_file_path()
            if config_file_path:
                config.read(config_file_path)
            cls._keys = {
                "palm2": cls._load_key("GOOGLE_API_KEY", config),
                "gemini-pro": cls._load_key("GOOGLE_API_KEY", config),
                "mistral": cls._load_key("MISTRAL_API_KEY", config),
                "openai": cls._load_key("OPENAI_API_KEY", config),
                "anthropic": cls._load_key("ANTHROPIC_API_KEY", config),
                "groq": cls._load_key("GROQ_API_KEY", config),
                "openrouter": cls._load_key("OPENROUTER_API_KEY", config),
                "ollama": cls._load_key("OLLAMA_API_KEY", config),
                "xai": cls._load_key("XAI_API_KEY", config),
                "my_llm": "mocked_api_key",
            }
        return cls._keys

    @classmethod
    def _resolve_config_file_path(cls) -> str | None:
        explicit_file = os.getenv("API_KEY_FILE")
        if explicit_file:
            return explicit_file

        config_file_directory = os.getenv("API_KEY_FILE_PATH")
        if config_file_directory:
            return os.path.join(config_file_directory, "api_key.conf")

        default_candidates = [
            "/run/secrets/api_key.conf",
            os.path.join(".", "api_key.conf"),
        ]
        for candidate in default_candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    @classmethod
    def _load_key(cls, env_name: str, config: ConfigParser) -> str | None:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        return config.get("API_KEYS", env_name, fallback=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_LLM(
    model: str | None = None,
    prompt: str = "",
    role: str | None = None,
    provider: str | None = None,
) -> str | dict[str, Any] | None:
    """Call an LLM using role-based routing or direct provider/model override.

    Success:
        returns plain text

    Failure:
        returns structured dict:
        {
          "ok": False,
          "error": {...}
        }
    """
    target = _resolve_target(model=model, role=role, provider=provider)

    if target.provider == "openai":
        api_key = APIKeyManager.load_keys().get("openai")
        if not api_key:
            return _error_response(
                code="missing_api_key",
                message="API key for provider 'openai' is missing.",
                provider="openai",
                model=target.model,
            )
        return _call_openai_responses(
            api_key=api_key,
            model_name=target.model,
            prompt=prompt,
            role=role,
        )

    if target.provider == "ollama":
        return _call_ollama_generate(
            model_name=target.model,
            prompt=prompt,
        )

    # Legacy providers remain supported
    api_keys = APIKeyManager.load_keys()
    api_key = api_keys.get(target.provider)
    if not api_key:
        return _error_response(
            code="missing_api_key",
            message=f"API key for provider '{target.provider}' is missing.",
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "palm2":
        return _legacy_json_completion(
            url=f"https://generativelanguage.googleapis.com/v1beta3/models/text-bison-001:generateText?key={api_key}",
            headers={"Content-Type": "application/json"},
            payload={"prompt": {"text": prompt}},
            extractor=lambda body: body.get("candidates", [{}])[0].get("output", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "gemini-pro":
        return _legacy_json_completion(
            url=(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-1.5-flash-latest:generateContent?key="
                f"{api_key}"
            ),
            headers={"Content-Type": "application/json"},
            payload={"contents": [{"parts": [{"text": prompt}]}]},
            extractor=lambda body: body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "mistral":
        return _legacy_json_completion(
            url="https://api.mistral.ai/v1/chat/completions",
            headers=_bearer_headers(api_key),
            payload={"model": "mistral-medium", "messages": [{"role": "user", "content": prompt}]},
            extractor=lambda body: body.get("choices", [{}])[0].get("message", {}).get("content", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "anthropic":
        return _legacy_json_completion(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": "claude-3-opus-20240229",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            extractor=lambda body: _extract_anthropic_text(body),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "groq":
        return _legacy_json_completion(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers=_bearer_headers(api_key),
            payload={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]},
            extractor=lambda body: body.get("choices", [{}])[0].get("message", {}).get("content", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "openrouter":
        headers = _bearer_headers(api_key)
        headers.update({
            "HTTP-Referer": os.getenv("AUTOCODA_OPENROUTER_REFERER", "https://example.com"),
            "X-Title": os.getenv("AUTOCODA_OPENROUTER_TITLE", "Autocoda"),
        })
        return _legacy_json_completion(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            payload={"model": target.model, "messages": [{"role": "user", "content": prompt}]},
            extractor=lambda body: body.get("choices", [{}])[0].get("message", {}).get("content", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "xai":
        return _legacy_json_completion(
            url="https://api.x.ai/v1/chat/completions",
            headers=_bearer_headers(api_key),
            payload={
                "model": "grok-beta",
                "stream": False,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            },
            extractor=lambda body: body.get("choices", [{}])[0].get("message", {}).get("content", ""),
            provider=target.provider,
            model=target.model,
        )

    if target.provider == "my_llm":
        return _legacy_json_completion(
            url=f"{OLLAMA_BASE_URL}/api/generate",
            headers={"Content-Type": "application/json"},
            payload={"model": "llama3", "stream": False, "prompt": prompt},
            extractor=lambda body: body.get("response", ""),
            provider=target.provider,
            model=target.model,
        )

    return _error_response(
        code="unsupported_target",
        message=f"Provider '{target.provider}' is not supported.",
        provider=target.provider,
        model=target.model,
    )


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def _resolve_target(
    model: str | None,
    role: str | None,
    provider: str | None,
) -> ResolvedTarget:
    """Resolve provider + concrete model.

    Resolution order:
    1. explicit provider override
    2. role default
    3. direct model argument
    4. fallback to OpenAI default
    """
    if provider == "ollama":
        chosen_model = model or _ollama_model_for_role(role)
        return ResolvedTarget(provider="ollama", model=chosen_model)

    if provider == "openai":
        chosen_model = model or _openai_model_for_role(role)
        return ResolvedTarget(provider="openai", model=chosen_model)

    if role and role in ROLE_DEFAULTS:
        role_config = ROLE_DEFAULTS[role]
        return ResolvedTarget(
            provider=role_config["provider"],
            model=role_config["model"],
        )

    if model in {None, "", "openai"}:
        return ResolvedTarget(
            provider="openai",
            model=os.getenv("AUTOCODA_OPENAI_MODEL", "gpt-5.1"),
        )

    # Backward-compatible direct provider/model mode
    if model in {"palm2", "gemini-pro", "mistral", "anthropic", "groq", "openrouter", "ollama", "xai", "my_llm"}:
        if model == "ollama":
            return ResolvedTarget(provider="ollama", model=OLLAMA_DEFAULT_MODEL)
        return ResolvedTarget(provider=model, model=model)

    # Assume unknown model means OpenRouter/OpenAI-style direct model usage is not supported here.
    # Treat it as an OpenAI model only if explicitly requested by provider.
    return ResolvedTarget(provider="openai", model=model)


def _openai_model_for_role(role: str | None) -> str:
    if role and role in ROLE_DEFAULTS:
        return ROLE_DEFAULTS[role]["model"]
    return os.getenv("AUTOCODA_OPENAI_MODEL", "gpt-5.1")


def _ollama_model_for_role(role: str | None) -> str:
    if role == "code_implementor":
        return os.getenv("AUTOCODA_OLLAMA_CODE_IMPLEMENTOR_MODEL", OLLAMA_DEFAULT_MODEL)
    if role == "coder":
        return os.getenv("AUTOCODA_OLLAMA_CODER_MODEL", OLLAMA_DEFAULT_MODEL)
    if role == "planner":
        return os.getenv("AUTOCODA_OLLAMA_PLANNER_MODEL", OLLAMA_DEFAULT_MODEL)
    if role == "manager":
        return os.getenv("AUTOCODA_OLLAMA_MANAGER_MODEL", OLLAMA_DEFAULT_MODEL)
    if role == "critic":
        return os.getenv("AUTOCODA_OLLAMA_CRITIC_MODEL", OLLAMA_DEFAULT_MODEL)
    return OLLAMA_DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def _call_openai_responses(
    api_key: str,
    model_name: str,
    prompt: str,
    role: str | None,
) -> str | dict[str, Any]:
    payload = {
        "model": model_name,
        "input": prompt,
        "reasoning": {"effort": _reasoning_effort_for_role(role)},
        "text": {"verbosity": "low"},
    }
    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers=_bearer_headers(api_key),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return _error_response(
            code="request_failed",
            message=str(exc),
            provider="openai",
            model=model_name,
        )

    body = response.json()
    output_text = body.get("output_text", "")
    if output_text:
        return output_text

    fallback_text = _extract_responses_api_text(body)
    if fallback_text:
        return fallback_text

    return _error_response(
        code="empty_output",
        message="OpenAI response did not contain output text.",
        provider="openai",
        model=model_name,
    )


def _call_ollama_generate(
    model_name: str,
    prompt: str,
) -> str | dict[str, Any] | None:
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return _error_response(
            code="request_failed",
            message=str(exc),
            provider="ollama",
            model=model_name,
        )

    try:
        body = response.json()
    except ValueError as exc:
        return _error_response(
            code="invalid_json",
            message=str(exc),
            provider="ollama",
            model=model_name,
        )

    text = body.get("response", "")
    if text:
        return text

    return _error_response(
        code="empty_output",
        message="Ollama response did not contain text output.",
        provider="ollama",
        model=model_name,
    )


def _legacy_json_completion(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    extractor: Callable[[dict[str, Any]], str],
    provider: str,
    model: str,
) -> str | dict[str, Any]:
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        return _error_response(
            code="request_failed",
            message=str(exc),
            provider=provider,
            model=model,
        )

    try:
        body = response.json()
    except ValueError as exc:
        return _error_response(
            code="invalid_json",
            message=str(exc),
            provider=provider,
            model=model,
        )

    text = extractor(body)
    if text:
        return text

    return _error_response(
        code="empty_output",
        message=f"{provider} response did not contain text output.",
        provider=provider,
        model=model,
    )


# ---------------------------------------------------------------------------
# Extractors / helpers
# ---------------------------------------------------------------------------

def _extract_responses_api_text(body: dict[str, Any]) -> str:
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    return ""


def _extract_anthropic_text(body: dict[str, Any]) -> str:
    parts = body.get("content", [])
    if not parts:
        return ""
    first = parts[0]
    if isinstance(first, dict):
        return first.get("text", "")
    return ""


def _bearer_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _reasoning_effort_for_role(role: str | None) -> str:
    if role == "manager":
        return "medium"
    if role == "code_implementor":
        return "low"
    if role == "coder":
        return "low"
    if role == "critic":
        return "medium"
    return "medium"


def _error_response(code: str, message: str, provider: str, model: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "provider": provider,
            "model": model,
        },
    }
