from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.market import MarketSnapshot


class FeatureSummary(BaseModel):
    latest_close: float = 0.0
    latest_return: float = 0.0
    ema12: float = 0.0
    ema26: float = 0.0
    rolling_volatility: float = 0.0
    macd: float = 0.0
    signal_line: float = 0.0
    macd_diff: float = 0.0
    lagged_macd: float = 0.0
    lagged_signal: float = 0.0
    predicted_macd: float = 0.0
    previous_predicted_macd: float = 0.0
    predicted_delta: float = 0.0
    confidence_raw: float = 0.0
    confidence_method: str = "unknown"
    regime_score: float = 0.0
    normalized_score: float = 0.0
    score_scale: float = 0.0
    persistence_ratio: float = 0.0
    policy_band: str = "flat"
    candles_used: int = 0
    feature_window: int = 0
    candle_interval_minutes: int = 0
    candle_source: str = "unknown"


class UniverseCandidate(BaseModel):
    symbol: str
    asset_class: str = "unclassified"
    asset_class_label: str = "Unclassified"
    live_tradeable: bool = True
    allocation_enabled: bool = True
    source: str = "unknown"
    latest_price: float = 0.0
    realized_volatility: float = 0.0
    average_dollar_volume: float = 0.0
    beta_to_btc: float = 0.0
    trend_quality: float = 0.0
    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    beta_score: float = 0.0
    trend_quality_score: float = 0.0
    regime_alignment_score: float = 0.0
    combined_universe_score: float = 0.0
    category: str = "unclassified"
    base_target_weight: float = 0.0
    target_weight: float = 0.0
    class_score: float = 0.0
    class_confidence: float = 0.0
    class_target_weight: float = 0.0
    selected: bool = False
    selected_within_class: bool = False
    selection_rank: int | None = None
    note: str = ""


class AssetClassAllocation(BaseModel):
    class_id: str
    label: str
    members: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    live_tradeable: bool = True
    allocation_enabled: bool = True
    class_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    average_trend: float = 0.0
    average_realized_volatility: float = 0.0
    relative_strength: float = 0.0
    drawdown: float = 0.0
    confidence_stability: float = 0.0
    category: str = "neutral"
    note: str = ""


class UniverseSelection(BaseModel):
    timestamp_ms: int
    reference_symbol: str = "BTCUSD"
    candidate_symbols: list[str] = Field(default_factory=list)
    selected_classes: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    selected_count: int = 0
    max_selected_assets: int = 0
    gross_target_weight: float = 0.0
    cash_reserve_weight: float = 1.0
    selection_reason: str = ""
    class_allocations: list[AssetClassAllocation] = Field(default_factory=list)
    candidates: list[UniverseCandidate] = Field(default_factory=list)


class TradingSignal(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    symbol: str = Field(..., examples=["BTCUSD"])
    signal: Literal["buy", "sell", "hold"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    base_target_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    target_weight: float = Field(..., ge=0.0, le=1.0)
    regime_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    asset_class: str = "unclassified"
    asset_class_label: str = "Unclassified"
    class_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    class_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    class_target_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    live_tradeable: bool = True
    exposure_state: Literal["flat", "light_long", "medium_long", "full_long"] = "flat"
    universe_score: float = Field(default=0.0, ge=0.0, le=1.0)
    universe_category: str = "unclassified"
    selection_rank: int | None = None
    selected_for_allocation: bool = False
    action_policy_reason: str = "No active exposure policy."
    model_version: str
    timestamp_ms: int
    engine_type: Literal["gru_packaged", "notebook_proxy"] = "notebook_proxy"
    artifact_status: str = "missing"
    artifact_loaded: bool = False
    artifact_path: str | None = None
    runtime_note: str | None = None
    features_summary: FeatureSummary
    inference_mode: Literal["gru_packaged", "notebook_proxy"] = "notebook_proxy"


class RiskDecision(BaseModel):
    symbol: str
    approved: bool
    side: Literal["buy", "sell", "hold"]
    size: float = Field(..., ge=0.0, le=1.0)
    target_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    current_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    rebalance_gap: float = Field(default=0.0, ge=-1.0, le=1.0)
    exposure_state: Literal["flat", "light_long", "medium_long", "full_long"] = "flat"
    action_policy: Literal["increase", "reduce", "flatten", "hold"] = "hold"
    reason: str
    timestamp_ms: int
    checks: dict[str, object] = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    mode: Literal["paper"]
    symbol: str
    side: Literal["buy", "sell", "hold"]
    target_weight: float = Field(..., ge=0.0, le=1.0)
    current_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    rebalance_gap: float = Field(default=0.0, ge=-1.0, le=1.0)
    exposure_state: Literal["flat", "light_long", "medium_long", "full_long"] = "flat"
    action_policy: Literal["increase", "reduce", "flatten", "hold"] = "hold"
    confidence: float = Field(..., ge=0.0, le=1.0)
    requested_at_ms: int
    reason: str


class ExecutionResult(BaseModel):
    status: Literal["filled", "rejected", "noop"]
    mode: Literal["paper"]
    symbol: str
    side: Literal["buy", "sell", "hold"]
    size: float = Field(..., ge=0.0, le=1.0)
    target_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    current_weight_before: float = Field(default=0.0, ge=0.0, le=1.0)
    current_weight_after: float = Field(default=0.0, ge=0.0, le=1.0)
    rebalance_gap: float = Field(default=0.0, ge=-1.0, le=1.0)
    exposure_state: Literal["flat", "light_long", "medium_long", "full_long"] = "flat"
    action_policy: Literal["increase", "reduce", "flatten", "hold"] = "hold"
    price: float = Field(default=0.0, ge=0.0)
    quantity: float = Field(default=0.0, ge=0.0)
    notional_usd: float = Field(default=0.0, ge=0.0)
    timestamp_ms: int
    reason: str


class PositionState(BaseModel):
    symbol: str
    quantity: float = Field(..., ge=0.0)
    avg_entry_price: float = Field(..., ge=0.0)
    market_price: float = Field(..., ge=0.0)
    market_value: float = Field(..., ge=0.0)
    unrealized_pnl: float
    realized_pnl: float = 0.0


class PnlState(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    net_pnl: float
    timestamp_ms: int


class PortfolioState(BaseModel):
    cash_usd: float = Field(..., ge=0.0)
    positions: list[PositionState]
    portfolio_value: float = Field(..., ge=0.0)
    realized_pnl: float
    unrealized_pnl: float
    timestamp_ms: int


class PortfolioCompositionEntry(BaseModel):
    symbol: str
    kind: Literal["asset", "cash"] = "asset"
    quantity: float | None = Field(default=None, ge=0.0)
    avg_entry_price: float | None = Field(default=None, ge=0.0)
    current_price: float = Field(default=0.0, ge=0.0)
    market_value: float = Field(default=0.0, ge=0.0)
    unrealized_pnl: float = 0.0
    actual_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    target_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_gap: float | None = Field(default=None, ge=-1.0, le=1.0)
    exposure_state: str | None = None
    category: str | None = None
    selected_for_allocation: bool = False
    last_fill_price: float | None = Field(default=None, ge=0.0)
    mark_vs_last_fill_bps: float | None = None


class TradingStatusResponse(BaseModel):
    pair: str
    market_source: str
    execution_mode: Literal["paper"]
    latest_universe: UniverseSelection | None = None
    latest_signals: list[TradingSignal] = Field(default_factory=list)
    latest_risk_decisions: list[RiskDecision] = Field(default_factory=list)
    latest_executions: list[ExecutionResult] = Field(default_factory=list)
    latest_signal: TradingSignal | None = None
    latest_risk_decision: RiskDecision | None = None
    latest_execution: ExecutionResult | None = None
    portfolio_composition: list[PortfolioCompositionEntry] = Field(default_factory=list)
    portfolio: PortfolioState
    pnl: PnlState


class TradingRunResponse(BaseModel):
    pair: str
    market_snapshot: MarketSnapshot
    universe: UniverseSelection | None = None
    market_snapshots: list[MarketSnapshot] = Field(default_factory=list)
    signals: list[TradingSignal] = Field(default_factory=list)
    risk_decisions: list[RiskDecision] = Field(default_factory=list)
    execution_requests: list[ExecutionRequest] = Field(default_factory=list)
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    signal: TradingSignal
    risk_decision: RiskDecision
    execution_request: ExecutionRequest
    execution_result: ExecutionResult
    portfolio: PortfolioState
    pnl: PnlState


class EngineState(BaseModel):
    running: bool
    mode: Literal["paper"]
    symbols: list[str]
    interval_seconds: int = Field(..., ge=5, le=3600)
    last_cycle_started_ms: int | None = None
    last_cycle_completed_ms: int | None = None
    last_cycle_status: Literal["idle", "running", "success", "error", "stopped"]
    last_error: str | None = None
    cycle_count: int = Field(default=0, ge=0)
    active_signal_engine_id: str = "notebook_proxy"
    signal_engine_type: str
    signal_model_version: str
    signal_artifact_status: str = "missing"
    signal_artifact_loaded: bool = False
    signal_artifact_path: str | None = None
    signal_runtime_note: str | None = None
    fallback_signal_engine_id: str = "notebook_proxy"
    latest_universe: UniverseSelection | None = None
    initial_paper_capital: float = Field(default=10000.0, ge=0.0)
    portfolio_source: Literal["initial_default", "persisted_runtime_state", "fresh_reset"] = "initial_default"
    state_persistence_enabled: bool = True
    execution_enabled: bool = True
    total_execution_count: int = Field(default=0, ge=0)
    total_noop_count: int = Field(default=0, ge=0)
    total_risk_rejection_count: int = Field(default=0, ge=0)
    reset_count: int = Field(default=0, ge=0)
    portfolio_reset_at_ms: int | None = None
    last_reset_reason: str | None = None
    last_signal_timestamp_ms: int | None = None
    last_execution_timestamp_ms: int | None = None
    last_execution_status: Literal["filled", "rejected", "noop"] | None = None
    last_cycle_outcome: str = "idle"


class EngineControlRequest(BaseModel):
    pair: str = Field(default="BTCUSD", min_length=3)
    interval_seconds: int = Field(default=60, ge=5, le=3600)


class EngineResetRequest(BaseModel):
    scope: Literal["all", "portfolio", "engine"] = "all"
    reason: str = Field(default="Operator requested a fresh paper experiment.", min_length=3)


class EngineStatusResponse(BaseModel):
    engine: EngineState
    running: bool
    mode: Literal["paper"]
    symbol_scope: list[str]
    interval_seconds: int
    cycle_count: int
    last_cycle_timestamp_ms: int | None = None
    last_signal_timestamp_ms: int | None = None
    last_execution_timestamp_ms: int | None = None
    active_signal_engine_id: str
    signal_engine_type: str
    signal_model_version: str
    signal_artifact_status: str
    signal_artifact_loaded: bool = False
    signal_artifact_path: str | None = None
    signal_runtime_note: str | None = None
    fallback_signal_engine_id: str = "notebook_proxy"
    latest_universe: UniverseSelection | None = None
    latest_signals: list[TradingSignal] = Field(default_factory=list)
    latest_risk_decisions: list[RiskDecision] = Field(default_factory=list)
    latest_executions: list[ExecutionResult] = Field(default_factory=list)
    initial_paper_capital: float
    portfolio_source: str
    portfolio_inherited: bool
    execution_enabled: bool
    state_persistence_enabled: bool
    total_execution_count: int
    total_noop_count: int
    total_risk_rejection_count: int
    last_cycle_outcome: str
    last_execution_status: str | None = None
    portfolio_reset_at_ms: int | None = None
    reset_count: int
    last_error: str | None = None
    market_source: str
    latest_signal: TradingSignal | None = None
    latest_risk_decision: RiskDecision | None = None
    latest_execution: ExecutionResult | None = None
    portfolio_composition: list[PortfolioCompositionEntry] = Field(default_factory=list)
    portfolio: PortfolioState
    pnl: PnlState
    operator_notes: list[str] = Field(default_factory=list)
