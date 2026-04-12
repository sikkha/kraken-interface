from __future__ import annotations

from pydantic import BaseModel, Field


class HistoryCycleRecord(BaseModel):
    id: int
    started_at_ms: int
    finished_at_ms: int | None = None
    symbol_scope: str
    market_source: str
    signal_engine_type: str
    interval_seconds: int
    cycle_outcome: str
    selected_classes: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    class_allocations: list[dict[str, object]] = Field(default_factory=list)
    error_message: str | None = None


class SignalHistoryRecord(BaseModel):
    id: int
    cycle_id: int
    timestamp_ms: int
    symbol: str
    signal: str
    confidence: float
    target_weight: float
    model_version: str
    engine_type: str
    artifact_status: str
    asset_class: str = "unclassified"
    asset_class_label: str = "Unclassified"
    class_score: float = 0.0
    class_confidence: float = 0.0
    class_target_weight: float = 0.0
    live_tradeable: bool = True
    base_target_weight: float = 0.0
    regime_score: float = 0.0
    exposure_state: str = "flat"
    universe_score: float = 0.0
    universe_category: str = "unclassified"
    selection_rank: int | None = None
    selected_for_allocation: bool = False
    action_policy_reason: str = ""
    features_summary: dict[str, object] = Field(default_factory=dict)


class RiskDecisionHistoryRecord(BaseModel):
    id: int
    cycle_id: int
    timestamp_ms: int
    symbol: str
    approved: bool
    side: str
    size: float
    target_weight: float = 0.0
    current_weight: float = 0.0
    rebalance_gap: float = 0.0
    exposure_state: str = "flat"
    action_policy: str = "hold"
    reason: str
    spread_bps: float | None = None
    cooldown_active: bool | None = None
    volatility_flag: bool | None = None


class ExecutionHistoryRecord(BaseModel):
    id: int
    cycle_id: int
    timestamp_ms: int
    mode: str
    status: str
    symbol: str
    side: str
    size: float
    target_weight: float = 0.0
    current_weight_before: float = 0.0
    current_weight_after: float = 0.0
    rebalance_gap: float = 0.0
    exposure_state: str = "flat"
    action_policy: str = "hold"
    price: float
    notional: float
    reason: str


class PortfolioSnapshotHistoryRecord(BaseModel):
    id: int
    cycle_id: int
    timestamp_ms: int
    cash_usd: float
    btc_qty: float
    avg_entry_price: float
    realized_pnl: float
    unrealized_pnl: float
    portfolio_value: float
    state_source: str
    positions: list[dict[str, object]] = Field(default_factory=list)


class HistoryCyclesResponse(BaseModel):
    db_path: str
    cycles: list[HistoryCycleRecord]


class HistorySignalsResponse(BaseModel):
    db_path: str
    signals: list[SignalHistoryRecord]


class HistoryRiskResponse(BaseModel):
    db_path: str
    decisions: list[RiskDecisionHistoryRecord]


class HistoryExecutionsResponse(BaseModel):
    db_path: str
    executions: list[ExecutionHistoryRecord]


class HistoryPortfolioResponse(BaseModel):
    db_path: str
    snapshots: list[PortfolioSnapshotHistoryRecord]
