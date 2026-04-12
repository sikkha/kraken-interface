from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.schemas.history import (
    ExecutionHistoryRecord,
    HistoryCycleRecord,
    PortfolioSnapshotHistoryRecord,
    RiskDecisionHistoryRecord,
    SignalHistoryRecord,
)
from backend.app.schemas.trading import ExecutionResult, PortfolioState, RiskDecision, TradingSignal, UniverseSelection


class SqliteHistoryLedger:
    def __init__(self) -> None:
        settings = get_settings()
        self.path = Path(settings.runtime_ledger_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS engine_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at_ms INTEGER NOT NULL,
                    finished_at_ms INTEGER,
                    symbol_scope TEXT NOT NULL,
                    selected_classes_json TEXT NOT NULL DEFAULT '[]',
                    selected_symbols_json TEXT NOT NULL DEFAULT '[]',
                    class_allocations_json TEXT NOT NULL DEFAULT '[]',
                    market_source TEXT NOT NULL,
                    signal_engine_type TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    cycle_outcome TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    base_target_weight REAL NOT NULL DEFAULT 0.0,
                    target_weight REAL NOT NULL,
                    model_version TEXT NOT NULL,
                    engine_type TEXT NOT NULL,
                    artifact_status TEXT NOT NULL,
                    asset_class TEXT NOT NULL DEFAULT 'unclassified',
                    asset_class_label TEXT NOT NULL DEFAULT 'Unclassified',
                    class_score REAL NOT NULL DEFAULT 0.0,
                    class_confidence REAL NOT NULL DEFAULT 0.0,
                    class_target_weight REAL NOT NULL DEFAULT 0.0,
                    live_tradeable INTEGER NOT NULL DEFAULT 1,
                    regime_score REAL NOT NULL DEFAULT 0.0,
                    exposure_state TEXT NOT NULL DEFAULT 'flat',
                    universe_score REAL NOT NULL DEFAULT 0.0,
                    universe_category TEXT NOT NULL DEFAULT 'unclassified',
                    selection_rank INTEGER,
                    selected_for_allocation INTEGER NOT NULL DEFAULT 0,
                    action_policy_reason TEXT NOT NULL DEFAULT '',
                    features_summary_json TEXT NOT NULL,
                    FOREIGN KEY (cycle_id) REFERENCES engine_cycles(id)
                );

                CREATE TABLE IF NOT EXISTS risk_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    symbol TEXT NOT NULL DEFAULT 'BTCUSD',
                    approved INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    target_weight REAL NOT NULL DEFAULT 0.0,
                    current_weight REAL NOT NULL DEFAULT 0.0,
                    rebalance_gap REAL NOT NULL DEFAULT 0.0,
                    exposure_state TEXT NOT NULL DEFAULT 'flat',
                    action_policy TEXT NOT NULL DEFAULT 'hold',
                    reason TEXT NOT NULL,
                    spread_bps REAL,
                    cooldown_active INTEGER,
                    volatility_flag INTEGER,
                    FOREIGN KEY (cycle_id) REFERENCES engine_cycles(id)
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    target_weight REAL NOT NULL DEFAULT 0.0,
                    current_weight_before REAL NOT NULL DEFAULT 0.0,
                    current_weight_after REAL NOT NULL DEFAULT 0.0,
                    rebalance_gap REAL NOT NULL DEFAULT 0.0,
                    exposure_state TEXT NOT NULL DEFAULT 'flat',
                    action_policy TEXT NOT NULL DEFAULT 'hold',
                    price REAL NOT NULL,
                    notional REAL NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY (cycle_id) REFERENCES engine_cycles(id)
                );

                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    cash_usd REAL NOT NULL,
                    btc_qty REAL NOT NULL,
                    avg_entry_price REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    portfolio_value REAL NOT NULL,
                    state_source TEXT NOT NULL,
                    positions_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY (cycle_id) REFERENCES engine_cycles(id)
                );
                """
            )
            self._ensure_column(connection, "engine_cycles", "selected_symbols_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "engine_cycles", "selected_classes_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "engine_cycles", "class_allocations_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "signals", "regime_score", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "base_target_weight", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "asset_class", "TEXT NOT NULL DEFAULT 'unclassified'")
            self._ensure_column(connection, "signals", "asset_class_label", "TEXT NOT NULL DEFAULT 'Unclassified'")
            self._ensure_column(connection, "signals", "class_score", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "class_confidence", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "class_target_weight", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "live_tradeable", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(connection, "signals", "exposure_state", "TEXT NOT NULL DEFAULT 'flat'")
            self._ensure_column(connection, "signals", "universe_score", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "signals", "universe_category", "TEXT NOT NULL DEFAULT 'unclassified'")
            self._ensure_column(connection, "signals", "selection_rank", "INTEGER")
            self._ensure_column(connection, "signals", "selected_for_allocation", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "signals", "action_policy_reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "risk_decisions", "symbol", "TEXT NOT NULL DEFAULT 'BTCUSD'")
            self._ensure_column(connection, "risk_decisions", "target_weight", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "risk_decisions", "current_weight", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "risk_decisions", "rebalance_gap", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "risk_decisions", "exposure_state", "TEXT NOT NULL DEFAULT 'flat'")
            self._ensure_column(connection, "risk_decisions", "action_policy", "TEXT NOT NULL DEFAULT 'hold'")
            self._ensure_column(connection, "executions", "target_weight", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "executions", "current_weight_before", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "executions", "current_weight_after", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "executions", "rebalance_gap", "REAL NOT NULL DEFAULT 0.0")
            self._ensure_column(connection, "executions", "exposure_state", "TEXT NOT NULL DEFAULT 'flat'")
            self._ensure_column(connection, "executions", "action_policy", "TEXT NOT NULL DEFAULT 'hold'")
            self._ensure_column(connection, "portfolio_snapshots", "positions_json", "TEXT NOT NULL DEFAULT '[]'")

    def record_successful_cycle(
        self,
        *,
        started_at_ms: int,
        finished_at_ms: int,
        symbol_scope: str,
        market_source: str,
        signal_engine_type: str,
        interval_seconds: int,
        cycle_outcome: str,
        universe: UniverseSelection | None,
        signals: list[TradingSignal],
        risk_decisions: list[RiskDecision],
        executions: list[ExecutionResult],
        portfolio: PortfolioState,
        portfolio_source: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO engine_cycles (
                    started_at_ms,
                    finished_at_ms,
                    symbol_scope,
                    selected_classes_json,
                    selected_symbols_json,
                    class_allocations_json,
                    market_source,
                    signal_engine_type,
                    interval_seconds,
                    cycle_outcome,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at_ms,
                    finished_at_ms,
                    symbol_scope,
                    json.dumps((universe.selected_classes if universe else []), sort_keys=True),
                    json.dumps((universe.selected_symbols if universe else []), sort_keys=True),
                    json.dumps(
                        ([allocation.model_dump() for allocation in universe.class_allocations] if universe else []),
                        sort_keys=True,
                    ),
                    market_source,
                    signal_engine_type,
                    interval_seconds,
                    cycle_outcome,
                    None,
                ),
            )
            cycle_id = int(cursor.lastrowid)
            for signal in signals:
                cursor.execute(
                    """
                    INSERT INTO signals (
                        cycle_id,
                        timestamp_ms,
                        symbol,
                        signal,
                        confidence,
                        base_target_weight,
                        target_weight,
                        model_version,
                        engine_type,
                        artifact_status,
                        asset_class,
                        asset_class_label,
                        class_score,
                        class_confidence,
                        class_target_weight,
                        live_tradeable,
                        regime_score,
                        exposure_state,
                        universe_score,
                        universe_category,
                        selection_rank,
                        selected_for_allocation,
                        action_policy_reason,
                        features_summary_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_id,
                        signal.timestamp_ms,
                        signal.symbol,
                        signal.signal,
                        signal.confidence,
                        signal.base_target_weight,
                        signal.target_weight,
                        signal.model_version,
                        signal.engine_type,
                        signal.artifact_status,
                        signal.asset_class,
                        signal.asset_class_label,
                        signal.class_score,
                        signal.class_confidence,
                        signal.class_target_weight,
                        int(signal.live_tradeable),
                        signal.regime_score,
                        signal.exposure_state,
                        signal.universe_score,
                        signal.universe_category,
                        signal.selection_rank,
                        int(signal.selected_for_allocation),
                        signal.action_policy_reason,
                        json.dumps(signal.features_summary.model_dump(), sort_keys=True),
                    ),
                )
            for risk_decision in risk_decisions:
                cursor.execute(
                    """
                    INSERT INTO risk_decisions (
                        cycle_id,
                        timestamp_ms,
                        symbol,
                        approved,
                        side,
                        size,
                        target_weight,
                        current_weight,
                        rebalance_gap,
                        exposure_state,
                        action_policy,
                        reason,
                        spread_bps,
                        cooldown_active,
                        volatility_flag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_id,
                        risk_decision.timestamp_ms,
                        risk_decision.symbol,
                        int(risk_decision.approved),
                        risk_decision.side,
                        risk_decision.size,
                        risk_decision.target_weight,
                        risk_decision.current_weight,
                        risk_decision.rebalance_gap,
                        risk_decision.exposure_state,
                        risk_decision.action_policy,
                        risk_decision.reason,
                        _coerce_float(risk_decision.checks.get("spread_bps")),
                        _coerce_bool(risk_decision.checks.get("cooldown_active")),
                        _coerce_bool(risk_decision.checks.get("volatility_flag")),
                    ),
                )
            for execution in executions:
                cursor.execute(
                    """
                    INSERT INTO executions (
                        cycle_id,
                        timestamp_ms,
                        mode,
                        status,
                        symbol,
                        side,
                        size,
                        target_weight,
                        current_weight_before,
                        current_weight_after,
                        rebalance_gap,
                        exposure_state,
                        action_policy,
                        price,
                        notional,
                        reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_id,
                        execution.timestamp_ms,
                        execution.mode,
                        execution.status,
                        execution.symbol,
                        execution.side,
                        execution.size,
                        execution.target_weight,
                        execution.current_weight_before,
                        execution.current_weight_after,
                        execution.rebalance_gap,
                        execution.exposure_state,
                        execution.action_policy,
                        execution.price,
                        execution.notional_usd,
                        execution.reason,
                    ),
                )
            cursor.execute(
                """
                INSERT INTO portfolio_snapshots (
                    cycle_id,
                    timestamp_ms,
                    cash_usd,
                    btc_qty,
                    avg_entry_price,
                    realized_pnl,
                    unrealized_pnl,
                    portfolio_value,
                    state_source,
                    positions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    portfolio.timestamp_ms,
                    portfolio.cash_usd,
                    _position_quantity(portfolio, "BTCUSD"),
                    _position_avg_entry(portfolio, "BTCUSD"),
                    portfolio.realized_pnl,
                    portfolio.unrealized_pnl,
                    portfolio.portfolio_value,
                    portfolio_source,
                    json.dumps([position.model_dump() for position in portfolio.positions], sort_keys=True),
                ),
            )
            connection.commit()
            return cycle_id

    def record_failed_cycle(
        self,
        *,
        started_at_ms: int,
        finished_at_ms: int,
        symbol_scope: str,
        market_source: str,
        signal_engine_type: str,
        interval_seconds: int,
        error_message: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO engine_cycles (
                    started_at_ms,
                    finished_at_ms,
                    symbol_scope,
                    selected_classes_json,
                    selected_symbols_json,
                    class_allocations_json,
                    market_source,
                    signal_engine_type,
                    interval_seconds,
                    cycle_outcome,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at_ms,
                    finished_at_ms,
                    symbol_scope,
                    json.dumps([], sort_keys=True),
                    json.dumps([], sort_keys=True),
                    json.dumps([], sort_keys=True),
                    market_source,
                    signal_engine_type,
                    interval_seconds,
                    "error",
                    error_message,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_cycles(self, limit: int = 50) -> list[HistoryCycleRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, started_at_ms, finished_at_ms, symbol_scope, selected_classes_json, selected_symbols_json,
                       class_allocations_json, market_source, signal_engine_type, interval_seconds, cycle_outcome,
                       error_message
                FROM engine_cycles
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            HistoryCycleRecord.model_validate(
                {
                    **dict(row),
                    "selected_classes": json.loads(row["selected_classes_json"] or "[]"),
                    "selected_symbols": json.loads(row["selected_symbols_json"] or "[]"),
                    "class_allocations": json.loads(row["class_allocations_json"] or "[]"),
                }
            )
            for row in rows
        ]

    def list_signals(self, limit: int = 50) -> list[SignalHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, cycle_id, timestamp_ms, symbol, signal, confidence, base_target_weight, target_weight,
                       model_version, engine_type, artifact_status, asset_class, asset_class_label,
                       class_score, class_confidence, class_target_weight, live_tradeable, regime_score,
                       exposure_state, universe_score, universe_category, selection_rank,
                       selected_for_allocation, action_policy_reason, features_summary_json
                FROM signals
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SignalHistoryRecord(
                id=row["id"],
                cycle_id=row["cycle_id"],
                timestamp_ms=row["timestamp_ms"],
                symbol=row["symbol"],
                signal=row["signal"],
                confidence=row["confidence"],
                base_target_weight=row["base_target_weight"],
                target_weight=row["target_weight"],
                model_version=row["model_version"],
                engine_type=row["engine_type"],
                artifact_status=row["artifact_status"],
                asset_class=row["asset_class"],
                asset_class_label=row["asset_class_label"],
                class_score=row["class_score"],
                class_confidence=row["class_confidence"],
                class_target_weight=row["class_target_weight"],
                live_tradeable=bool(row["live_tradeable"]),
                regime_score=row["regime_score"],
                exposure_state=row["exposure_state"],
                universe_score=row["universe_score"],
                universe_category=row["universe_category"],
                selection_rank=row["selection_rank"],
                selected_for_allocation=bool(row["selected_for_allocation"]),
                action_policy_reason=row["action_policy_reason"],
                features_summary=json.loads(row["features_summary_json"]),
            )
            for row in rows
        ]

    def list_risk_decisions(self, limit: int = 50) -> list[RiskDecisionHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, cycle_id, timestamp_ms, symbol, approved, side, size,
                       target_weight, current_weight, rebalance_gap, exposure_state,
                       action_policy, reason,
                       spread_bps, cooldown_active, volatility_flag
                FROM risk_decisions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RiskDecisionHistoryRecord(
                id=row["id"],
                cycle_id=row["cycle_id"],
                timestamp_ms=row["timestamp_ms"],
                symbol=row["symbol"],
                approved=bool(row["approved"]),
                side=row["side"],
                size=row["size"],
                target_weight=row["target_weight"],
                current_weight=row["current_weight"],
                rebalance_gap=row["rebalance_gap"],
                exposure_state=row["exposure_state"],
                action_policy=row["action_policy"],
                reason=row["reason"],
                spread_bps=row["spread_bps"],
                cooldown_active=_sqlite_bool(row["cooldown_active"]),
                volatility_flag=_sqlite_bool(row["volatility_flag"]),
            )
            for row in rows
        ]

    def list_executions(self, limit: int = 50) -> list[ExecutionHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, cycle_id, timestamp_ms, mode, status, symbol, side, size,
                       target_weight, current_weight_before, current_weight_after,
                       rebalance_gap, exposure_state, action_policy, price, notional, reason
                FROM executions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [ExecutionHistoryRecord.model_validate(dict(row)) for row in rows]

    def list_portfolio_snapshots(self, limit: int = 200) -> list[PortfolioSnapshotHistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, cycle_id, timestamp_ms, cash_usd, btc_qty, avg_entry_price,
                       realized_pnl, unrealized_pnl, portfolio_value, state_source, positions_json
                FROM portfolio_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            PortfolioSnapshotHistoryRecord.model_validate(
                {
                    **dict(row),
                    "positions": json.loads(row["positions_json"] or "[]"),
                }
            )
            for row in rows
        ]

    def database_path(self) -> str:
        return str(self.path)

    def reset_database(self) -> None:
        for candidate in (self.path, self.path.with_name(f"{self.path.name}-wal"), self.path.with_name(f"{self.path.name}-shm")):
            if candidate.exists():
                os.remove(candidate)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def initialize_history_ledger() -> SqliteHistoryLedger:
    ledger = SqliteHistoryLedger()
    ledger.initialize()
    return ledger


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _coerce_bool(value: object) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def _sqlite_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _position_quantity(portfolio: PortfolioState, symbol: str) -> float:
    for position in portfolio.positions:
        if position.symbol == symbol:
            return position.quantity
    return 0.0


def _position_avg_entry(portfolio: PortfolioState, symbol: str) -> float:
    for position in portfolio.positions:
        if position.symbol == symbol:
            return position.avg_entry_price
    return 0.0
