from pydantic import BaseModel


class AdapterStatus(BaseModel):
    name: str
    role: str
    ready: bool
    mode: str
    notes: str


class EventRecord(BaseModel):
    timestamp_ms: int
    level: str
    component: str
    message: str
    data: dict[str, str] | dict[str, int] | dict[str, float] | dict[str, bool] | dict[str, object] | None = None


class SystemStatus(BaseModel):
    mode: str
    readiness: str
    market_source: str
    ai_route: str
    adapters: list[AdapterStatus]
    recent_events: list[EventRecord]
