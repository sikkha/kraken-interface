from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import RLock
from typing import Any

from backend.app.schemas.market import MarketSnapshot
from backend.app.core.config import get_settings
from backend.app.schemas.trading import (
    EngineState,
    ExecutionResult,
    PortfolioState,
    RiskDecision,
    TradingSignal,
    UniverseSelection,
)


_STATE_LOCK = RLock()


class JsonStateStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.root = Path(settings.runtime_state_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def load_signal(self) -> TradingSignal | None:
        payload = self._load_json("latest_signal.json")
        return TradingSignal.model_validate(payload) if payload else None

    def save_signal(self, signal: TradingSignal) -> None:
        self._save_json("latest_signal.json", signal.model_dump())

    def load_signals(self) -> list[TradingSignal]:
        payload = self._load_json("latest_signals.json")
        if not payload:
            signal = self.load_signal()
            return [signal] if signal else []
        return [TradingSignal.model_validate(item) for item in payload.get("signals", [])]

    def save_signals(self, signals: list[TradingSignal]) -> None:
        self._save_json("latest_signals.json", {"signals": [signal.model_dump() for signal in signals]})
        if signals:
            self.save_signal(signals[0])

    def load_risk_decision(self) -> RiskDecision | None:
        payload = self._load_json("latest_risk_decision.json")
        return RiskDecision.model_validate(self._normalize_risk_payload(payload)) if payload else None

    def save_risk_decision(self, decision: RiskDecision) -> None:
        self._save_json("latest_risk_decision.json", decision.model_dump())

    def load_risk_decisions(self) -> list[RiskDecision]:
        payload = self._load_json("latest_risk_decisions.json")
        if not payload:
            decision = self.load_risk_decision()
            return [decision] if decision else []
        return [RiskDecision.model_validate(self._normalize_risk_payload(item)) for item in payload.get("decisions", [])]

    def save_risk_decisions(self, decisions: list[RiskDecision]) -> None:
        self._save_json("latest_risk_decisions.json", {"decisions": [decision.model_dump() for decision in decisions]})
        if decisions:
            self.save_risk_decision(decisions[0])

    def load_execution(self) -> ExecutionResult | None:
        payload = self._load_json("latest_execution.json")
        return ExecutionResult.model_validate(payload) if payload else None

    def save_execution(self, execution: ExecutionResult) -> None:
        self._save_json("latest_execution.json", execution.model_dump())

    def load_executions(self) -> list[ExecutionResult]:
        payload = self._load_json("latest_executions.json")
        if not payload:
            execution = self.load_execution()
            return [execution] if execution else []
        return [ExecutionResult.model_validate(item) for item in payload.get("executions", [])]

    def save_executions(self, executions: list[ExecutionResult]) -> None:
        self._save_json("latest_executions.json", {"executions": [execution.model_dump() for execution in executions]})
        if executions:
            self.save_execution(executions[0])

    def load_market_snapshot(self) -> MarketSnapshot | None:
        payload = self._load_json("latest_market_snapshot.json")
        return MarketSnapshot.model_validate(payload) if payload else None

    def save_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._save_json("latest_market_snapshot.json", snapshot.model_dump())

    def load_market_snapshots(self) -> list[MarketSnapshot]:
        payload = self._load_json("latest_market_snapshots.json")
        if not payload:
            snapshot = self.load_market_snapshot()
            return [snapshot] if snapshot else []
        return [MarketSnapshot.model_validate(item) for item in payload.get("snapshots", [])]

    def save_market_snapshots(self, snapshots: list[MarketSnapshot]) -> None:
        self._save_json("latest_market_snapshots.json", {"snapshots": [snapshot.model_dump() for snapshot in snapshots]})
        if snapshots:
            self.save_market_snapshot(snapshots[0])

    def load_portfolio(self) -> PortfolioState:
        payload = self._load_json("portfolio.json")
        if payload:
            return PortfolioState.model_validate(payload)
        return self.build_initial_portfolio()

    def save_portfolio(self, portfolio: PortfolioState) -> None:
        self._save_json("portfolio.json", portfolio.model_dump())

    def load_engine_state(self) -> EngineState | None:
        payload = self._load_json("engine_state.json")
        return EngineState.model_validate(payload) if payload else None

    def save_engine_state(self, engine_state: EngineState) -> None:
        self._save_json("engine_state.json", engine_state.model_dump())

    def load_universe(self) -> UniverseSelection | None:
        payload = self._load_json("latest_universe.json")
        return UniverseSelection.model_validate(payload) if payload else None

    def save_universe(self, universe: UniverseSelection) -> None:
        self._save_json("latest_universe.json", universe.model_dump())

    def has_state_file(self, filename: str) -> bool:
        return (self.root / filename).exists()

    def delete_state_files(self, *filenames: str) -> None:
        with _STATE_LOCK:
            for filename in filenames:
                path = self.root / filename
                if path.exists():
                    path.unlink()

    def build_initial_portfolio(self) -> PortfolioState:
        settings = get_settings()
        timestamp_ms = int(time.time() * 1000)
        return PortfolioState(
            cash_usd=settings.paper_starting_cash_usd,
            positions=[],
            portfolio_value=settings.paper_starting_cash_usd,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            timestamp_ms=timestamp_ms,
        )

    def _load_json(self, filename: str) -> dict[str, Any] | None:
        path = self.root / filename
        with _STATE_LOCK:
            if not path.exists():
                return None
            return json.loads(path.read_text())

    def _save_json(self, filename: str, payload: dict[str, Any]) -> None:
        path = self.root / filename
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        with _STATE_LOCK:
            temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
            os.replace(temporary_path, path)

    def _normalize_risk_payload(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not payload:
            return payload
        if "symbol" in payload:
            return payload
        settings = get_settings()
        return {**payload, "symbol": settings.default_pair}
