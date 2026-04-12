from __future__ import annotations

from backend.app.adapters.account import AccountAdapter
from backend.app.adapters.execution import ExecutionAdapter
from backend.app.adapters.kraken_market import KrakenMarketAdapter
from backend.app.adapters.strategy import StrategyAdapter
from backend.app.core.config import get_settings
from backend.app.schemas.system import AdapterStatus, SystemStatus
from backend.app.services.event_log import get_recent_events


def get_system_status() -> SystemStatus:
    settings = get_settings()
    recent_events = get_recent_events()
    market_adapter = KrakenMarketAdapter(source_mode=settings.kraken_market_source)
    market_adapter_status = AdapterStatus.model_validate(market_adapter.status())
    adapters = [
        market_adapter_status,
        AdapterStatus.model_validate(AccountAdapter().status()),
        AdapterStatus.model_validate(ExecutionAdapter().status()),
        AdapterStatus.model_validate(StrategyAdapter().status()),
    ]
    market_failure_seen = any(
        event["component"] == "market" and event["level"] == "ERROR"
        for event in recent_events
    )

    if settings.kraken_market_source == "mock":
        readiness = "scaffold-ready"
    elif market_adapter_status.ready and not market_failure_seen:
        readiness = "live-ready"
    else:
        readiness = "degraded"

    return SystemStatus(
        mode=settings.system_mode,
        readiness=readiness,
        market_source=settings.kraken_market_source,
        ai_route="library.llm_handler",
        adapters=adapters,
        recent_events=recent_events,
    )
