from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger("trading_workstation")
_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)


def emit_event(level: str, component: str, message: str, data: dict[str, Any] | None = None) -> None:
    normalized_level = level.upper()
    record = {
        "timestamp_ms": int(time.time() * 1000),
        "level": normalized_level,
        "component": component,
        "message": message,
        "data": data,
    }
    _EVENTS.appendleft(record)
    logger.log(getattr(logging, normalized_level, logging.INFO), "%s | %s | %s", component, message, data or {})


def get_recent_events(limit: int = 10) -> list[dict[str, Any]]:
    return list(_EVENTS)[:limit]
