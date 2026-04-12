from __future__ import annotations

import threading
import time

from backend.app.core.config import get_settings
from backend.app.schemas.trading import (
    EngineControlRequest,
    EngineResetRequest,
    ExecutionResult,
    EngineState,
    EngineStatusResponse,
    PortfolioCompositionEntry,
    PortfolioState,
    TradingRunResponse,
    TradingSignal,
    UniverseSelection,
)
from backend.app.services.event_log import emit_event
from backend.app.services.history_ledger import SqliteHistoryLedger
from backend.app.services.paper_execution_service import portfolio_to_pnl
from backend.app.signal_engine import load_signal_artifact
from backend.app.services.state_store import JsonStateStore
from backend.app.services.trading_loop_service import run_trading_cycle


_SERVICE_LOCK = threading.RLock()
_CYCLE_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()
_ENGINE_THREAD: threading.Thread | None = None


def initialize_engine_state() -> None:
    store = JsonStateStore()
    state = store.load_engine_state()
    if state is None:
        portfolio_source = "persisted_runtime_state" if store.has_state_file("portfolio.json") else "initial_default"
        store.save_engine_state(_default_engine_state(portfolio_source=portfolio_source))
        return

    if state.running:
        store.save_engine_state(
            state.model_copy(
                update={
                    "running": False,
                    "last_cycle_status": "stopped",
                    "last_error": "Engine reset on backend startup.",
                    "portfolio_source": "persisted_runtime_state",
                }
            )
        )
        return

    if state.portfolio_source != "fresh_reset":
        store.save_engine_state(state.model_copy(update={"portfolio_source": "persisted_runtime_state"}))


def shutdown_engine() -> None:
    stop_engine()


def get_engine_status() -> EngineStatusResponse:
    settings = get_settings()
    store = JsonStateStore()
    engine = store.load_engine_state() or _default_engine_state(
        portfolio_source="persisted_runtime_state" if store.has_state_file("portfolio.json") else "initial_default"
    )
    if not engine.signal_artifact_path:
        engine = engine.model_copy(update={"signal_artifact_path": settings.signal_artifact_path})
    portfolio = store.load_portfolio()
    pnl = portfolio_to_pnl(portfolio)
    latest_signal = store.load_signal()
    latest_signals = store.load_signals()
    latest_risk_decision = store.load_risk_decision()
    latest_risk_decisions = store.load_risk_decisions()
    latest_execution = store.load_execution()
    latest_executions = store.load_executions()
    latest_universe = store.load_universe() or engine.latest_universe
    portfolio_composition = _build_portfolio_composition(
        portfolio=portfolio,
        latest_universe=latest_universe,
        latest_signals=latest_signals,
        latest_executions=latest_executions,
    )
    return EngineStatusResponse(
        engine=engine,
        running=engine.running,
        mode=engine.mode,
        symbol_scope=engine.symbols,
        interval_seconds=engine.interval_seconds,
        cycle_count=engine.cycle_count,
        last_cycle_timestamp_ms=engine.last_cycle_completed_ms,
        last_signal_timestamp_ms=engine.last_signal_timestamp_ms,
        last_execution_timestamp_ms=engine.last_execution_timestamp_ms,
        active_signal_engine_id=engine.active_signal_engine_id,
        signal_engine_type=engine.signal_engine_type,
        signal_model_version=engine.signal_model_version,
        signal_artifact_status=engine.signal_artifact_status,
        signal_artifact_loaded=engine.signal_artifact_loaded,
        signal_artifact_path=engine.signal_artifact_path,
        signal_runtime_note=engine.signal_runtime_note,
        fallback_signal_engine_id=engine.fallback_signal_engine_id,
        latest_universe=latest_universe,
        latest_signals=latest_signals,
        latest_risk_decisions=latest_risk_decisions,
        latest_executions=latest_executions,
        initial_paper_capital=engine.initial_paper_capital,
        portfolio_source=engine.portfolio_source,
        portfolio_inherited=engine.portfolio_source == "persisted_runtime_state",
        execution_enabled=engine.execution_enabled,
        state_persistence_enabled=engine.state_persistence_enabled,
        total_execution_count=engine.total_execution_count,
        total_noop_count=engine.total_noop_count,
        total_risk_rejection_count=engine.total_risk_rejection_count,
        last_cycle_outcome=engine.last_cycle_outcome,
        last_execution_status=engine.last_execution_status,
        portfolio_reset_at_ms=engine.portfolio_reset_at_ms,
        reset_count=engine.reset_count,
        last_error=engine.last_error,
        market_source=settings.kraken_market_source,
        latest_signal=latest_signal,
        latest_risk_decision=latest_risk_decision,
        latest_execution=latest_execution,
        portfolio_composition=portfolio_composition,
        portfolio=portfolio,
        pnl=pnl,
        operator_notes=_operator_notes(engine),
    )


def run_engine_once(pair: str | None = None, trigger: str = "manual") -> TradingRunResponse:
    with _CYCLE_LOCK:
        store = JsonStateStore()
        current = store.load_engine_state() or _default_engine_state()
        target_pair = (pair or current.symbols[0] or get_settings().default_pair).upper()
        started_at = int(time.time() * 1000)
        _save_engine_state(
            current.model_copy(
                update={
                    "symbols": [target_pair],
                    "last_cycle_started_ms": started_at,
                    "last_cycle_status": "running",
                    "last_error": None,
                }
            )
        )
        emit_event(
            level="INFO",
            component="engine",
            message="Trading cycle started.",
            data={"pair": target_pair, "trigger": trigger, "mode": "paper"},
        )
        try:
            result = run_trading_cycle(pair=target_pair, trigger=trigger)
        except Exception as exc:
            failed_at = int(time.time() * 1000)
            latest = store.load_engine_state() or current
            _save_engine_state(
                latest.model_copy(
                    update={
                    "last_cycle_completed_ms": failed_at,
                    "last_cycle_status": "error",
                    "last_error": str(exc),
                    "last_cycle_outcome": "error",
                }
            )
        )
            emit_event(
                level="ERROR",
                component="engine",
                message="Trading cycle failed.",
                data={"pair": target_pair, "trigger": trigger, "error": str(exc)},
            )
            _record_failed_history(
                started_at_ms=started_at,
                finished_at_ms=failed_at,
                symbol_scope=target_pair,
                interval_seconds=current.interval_seconds,
                signal_engine_type=(latest.signal_engine_type or current.signal_engine_type),
                error_message=str(exc),
            )
            raise

        completed_at = int(time.time() * 1000)
        latest = store.load_engine_state() or current
        _save_engine_state(
            latest.model_copy(
                update={
                    "symbols": [target_pair],
                    "last_cycle_completed_ms": completed_at,
                    "last_cycle_status": "success",
                    "last_error": None,
                    "cycle_count": latest.cycle_count + 1,
                    "symbols": result.universe.selected_symbols or [target_pair],
                    "active_signal_engine_id": result.signal.engine_type,
                    "signal_engine_type": result.signal.engine_type,
                    "signal_model_version": result.signal.model_version,
                    "signal_artifact_status": result.signal.artifact_status,
                    "signal_artifact_loaded": result.signal.artifact_loaded,
                    "signal_artifact_path": result.signal.artifact_path,
                    "signal_runtime_note": result.signal.runtime_note,
                    "latest_universe": result.universe,
                    "last_signal_timestamp_ms": result.signal.timestamp_ms,
                    "last_execution_timestamp_ms": result.execution_result.timestamp_ms,
                    "last_execution_status": result.execution_result.status,
                    "last_cycle_outcome": _cycle_outcome(result),
                    "total_execution_count": latest.total_execution_count
                    + (1 if result.execution_result.status == "filled" else 0),
                    "total_noop_count": latest.total_noop_count
                    + (1 if result.execution_result.status == "noop" else 0),
                    "total_risk_rejection_count": latest.total_risk_rejection_count
                    + (1 if not result.risk_decision.approved else 0),
                }
            )
        )
        emit_event(
            level="INFO",
            component="engine",
            message="Trading cycle finished.",
            data={
                "pair": target_pair,
                "trigger": trigger,
                "execution_status": result.execution_result.status,
                "portfolio_value": result.portfolio.portfolio_value,
            },
        )
        _record_successful_history(
            started_at_ms=started_at,
            finished_at_ms=completed_at,
            symbol_scope=target_pair,
            interval_seconds=latest.interval_seconds,
            portfolio_source=latest.portfolio_source,
            result=result,
        )
        return result


def start_engine(request: EngineControlRequest) -> EngineStatusResponse:
    global _ENGINE_THREAD
    with _SERVICE_LOCK:
        settings = get_settings()
        store = JsonStateStore()
        current = store.load_engine_state() or _default_engine_state()
        if current.running and _ENGINE_THREAD and _ENGINE_THREAD.is_alive():
            return get_engine_status()

        _STOP_EVENT.clear()
        target_pair = request.pair.upper()
        next_state = current.model_copy(
            update={
                "running": True,
                "mode": "paper",
                "symbols": [target_pair],
                "interval_seconds": request.interval_seconds,
                "last_cycle_status": "idle" if current.cycle_count == 0 else current.last_cycle_status,
                "last_error": None,
            }
        )
        _save_engine_state(next_state)
        _ENGINE_THREAD = threading.Thread(
            target=_run_background_loop,
            args=(target_pair, request.interval_seconds),
            name="paper-engine-loop",
            daemon=True,
        )
        _ENGINE_THREAD.start()
        emit_event(
            level="INFO",
            component="engine",
            message="Paper engine started.",
            data={
                "pair": target_pair,
                "interval_seconds": request.interval_seconds,
                "system_mode": settings.system_mode,
            },
        )
        return get_engine_status()


def stop_engine() -> EngineStatusResponse:
    global _ENGINE_THREAD
    with _SERVICE_LOCK:
        store = JsonStateStore()
        _STOP_EVENT.set()
        thread = _ENGINE_THREAD
        if thread and thread.is_alive():
            thread.join(timeout=2.5)
        _ENGINE_THREAD = None
        current = store.load_engine_state() or _default_engine_state()
        stopped_state = current.model_copy(
            update={
                "running": False,
                "last_cycle_status": "stopped" if current.last_cycle_status != "error" else current.last_cycle_status,
            }
        )
        _save_engine_state(stopped_state)
        emit_event(
            level="INFO",
            component="engine",
            message="Paper engine stopped.",
            data={"pair": stopped_state.symbols[0], "mode": stopped_state.mode},
        )
        return get_engine_status()


def reset_engine_state(request: EngineResetRequest) -> EngineStatusResponse:
    stop_engine()
    settings = get_settings()
    store = JsonStateStore()
    ledger = SqliteHistoryLedger()
    reset_timestamp_ms = int(time.time() * 1000)

    if request.scope in {"all", "portfolio"}:
        store.save_portfolio(store.build_initial_portfolio())
        store.delete_state_files(
            "latest_execution.json",
            "latest_executions.json",
            "latest_market_snapshot.json",
            "latest_market_snapshots.json",
            "latest_universe.json",
        )
        if request.scope == "all":
            store.delete_state_files(
                "latest_signal.json",
                "latest_signals.json",
                "latest_risk_decision.json",
                "latest_risk_decisions.json",
            )
            ledger.reset_database()

    if request.scope in {"all", "engine"}:
        previous = store.load_engine_state()
        next_reset_count = (previous.reset_count if previous else 0) + 1
        store.save_engine_state(
            _default_engine_state(
                portfolio_source="fresh_reset" if request.scope in {"all", "portfolio"} else "persisted_runtime_state"
            ).model_copy(
                update={
                    "reset_count": next_reset_count,
                    "portfolio_reset_at_ms": reset_timestamp_ms if request.scope in {"all", "portfolio"} else previous.portfolio_reset_at_ms if previous else None,
                    "last_reset_reason": request.reason,
                }
            )
        )
    else:
        current = store.load_engine_state() or _default_engine_state()
        store.save_engine_state(
            current.model_copy(
                update={
                    "portfolio_source": "fresh_reset",
                    "portfolio_reset_at_ms": reset_timestamp_ms,
                    "last_reset_reason": request.reason,
                    "reset_count": current.reset_count + 1,
                    "last_execution_timestamp_ms": None,
                    "last_execution_status": None,
                    "total_execution_count": 0,
                    "total_noop_count": 0,
                    "total_risk_rejection_count": 0,
                }
            )
        )

    emit_event(
        level="WARNING",
        component="engine",
        message="Paper experiment state reset.",
        data={
            "scope": request.scope,
            "reason": request.reason,
            "initial_paper_capital": settings.paper_starting_cash_usd,
            "ledger_reset": request.scope == "all",
            "ledger_path": ledger.database_path(),
        },
    )
    return get_engine_status()


def build_copilot_context() -> str:
    status = get_engine_status()
    latest_signal = status.latest_signal
    latest_risk = status.latest_risk_decision
    latest_execution = status.latest_execution
    position = status.portfolio.positions[0] if status.portfolio.positions else None

    return "\n".join(
        [
            "Trading engine context:",
            f"- engine_running: {status.engine.running}",
            f"- engine_mode: {status.engine.mode}",
            f"- symbol_scope: {','.join(status.engine.symbols)}",
            f"- selected_symbols: {','.join(status.latest_universe.selected_symbols) if status.latest_universe else 'none'}",
            f"- selected_classes: {','.join(status.latest_universe.selected_classes) if status.latest_universe else 'none'}",
            f"- interval_seconds: {status.engine.interval_seconds}",
            f"- signal_engine_type: {status.engine.signal_engine_type}",
            f"- signal_model_version: {status.engine.signal_model_version}",
            f"- signal_artifact_status: {status.engine.signal_artifact_status}",
            f"- signal_artifact_loaded: {status.engine.signal_artifact_loaded}",
            f"- signal_artifact_path: {status.engine.signal_artifact_path or 'none'}",
            f"- signal_runtime_note: {status.engine.signal_runtime_note or 'none'}",
            f"- portfolio_source: {status.portfolio_source}",
            f"- initial_paper_capital: {status.initial_paper_capital}",
            f"- market_source: {status.market_source}",
            f"- latest_signal: {latest_signal.signal if latest_signal else 'none'}",
            f"- latest_signal_confidence: {latest_signal.confidence if latest_signal else 'n/a'}",
            f"- latest_signal_target_weight: {latest_signal.target_weight if latest_signal else 'n/a'}",
            f"- latest_signal_exposure_state: {latest_signal.exposure_state if latest_signal else 'n/a'}",
            f"- latest_risk_decision: {latest_risk.reason if latest_risk else 'none'}",
            f"- latest_risk_action_policy: {latest_risk.action_policy if latest_risk else 'none'}",
            f"- latest_execution_status: {latest_execution.status if latest_execution else 'none'}",
            f"- latest_execution_action_policy: {latest_execution.action_policy if latest_execution else 'none'}",
            f"- cash_usd: {status.portfolio.cash_usd}",
            f"- portfolio_value: {status.portfolio.portfolio_value}",
            f"- realized_pnl: {status.pnl.realized_pnl}",
            f"- unrealized_pnl: {status.pnl.unrealized_pnl}",
            f"- lead_position_symbol: {position.symbol if position else 'none'}",
            f"- lead_position_quantity: {position.quantity if position else 0.0}",
            f"- lead_avg_entry_price: {position.avg_entry_price if position else 0.0}",
        ]
    )


def _run_background_loop(pair: str, interval_seconds: int) -> None:
    while not _STOP_EVENT.is_set():
        try:
            run_engine_once(pair=pair, trigger="loop")
        except Exception:
            pass

        if _STOP_EVENT.wait(interval_seconds):
            break

    store = JsonStateStore()
    current = store.load_engine_state() or _default_engine_state()
    _save_engine_state(current.model_copy(update={"running": False, "last_cycle_status": "stopped"}))


def _default_engine_state(portfolio_source: str = "initial_default") -> EngineState:
    settings = get_settings()
    artifact_status, _ = load_signal_artifact()
    return EngineState(
        running=False,
        mode="paper",
        symbols=[settings.default_pair],
        interval_seconds=settings.engine_default_interval_seconds,
        last_cycle_started_ms=None,
        last_cycle_completed_ms=None,
        last_cycle_status="idle",
        last_error=None,
        cycle_count=0,
        active_signal_engine_id=artifact_status.engine_type,
        signal_engine_type=artifact_status.engine_type,
        signal_model_version=artifact_status.model_version,
        signal_artifact_status=artifact_status.status,
        signal_artifact_loaded=artifact_status.loaded,
        signal_artifact_path=artifact_status.path or settings.signal_artifact_path,
        signal_runtime_note=artifact_status.reason,
        fallback_signal_engine_id="notebook_proxy",
        latest_universe=None,
        initial_paper_capital=settings.paper_starting_cash_usd,
        portfolio_source=portfolio_source,
        state_persistence_enabled=True,
        execution_enabled=True,
        total_execution_count=0,
        total_noop_count=0,
        total_risk_rejection_count=0,
        reset_count=0,
        portfolio_reset_at_ms=None,
        last_reset_reason=None,
        last_signal_timestamp_ms=None,
        last_execution_timestamp_ms=None,
        last_execution_status=None,
        last_cycle_outcome="idle",
    )


def _save_engine_state(state: EngineState) -> None:
    JsonStateStore().save_engine_state(state)


def _cycle_outcome(result: TradingRunResponse) -> str:
    if any(execution.status == "filled" for execution in result.execution_results):
        actions = sorted({execution.action_policy for execution in result.execution_results if execution.status == "filled"})
        return f"execution:{'+'.join(actions)}"
    if all(not decision.approved for decision in result.risk_decisions):
        actions = sorted({decision.action_policy for decision in result.risk_decisions})
        if actions == ["hold"]:
            return "rebalance_not_needed"
        return f"risk_rejected:{'+'.join(actions)}"
    return result.execution_result.status


def _operator_notes(engine: EngineState) -> list[str]:
    return [
        "Run Once executes exactly one full paper-engine cycle.",
        "Start begins continuous looping at the configured interval until Stop is used.",
        "Stop prevents future cycles and preserves current runtime_state files.",
        "Reset Experiment now wipes both latest-state JSON and the SQLite ledger so the next run starts clean.",
        "Each cycle now scores asset classes first, assigns class weights, then selects live assets inside approved classes.",
        "Cash is now an active reserve class rather than passive leftover inactivity.",
        "The dynamic long/flat policy compares final asset target weights to current portfolio weights on every cycle.",
        "Risk approval determines whether a cycle increases, reduces, flattens, or noops each paper position.",
        f"Active signal engine: {engine.active_signal_engine_id} | fallback path: {engine.fallback_signal_engine_id}.",
        f"Artifact status: {engine.signal_artifact_status} | runtime note: {engine.signal_runtime_note or 'none'}.",
    ]


def _build_portfolio_composition(
    *,
    portfolio: PortfolioState,
    latest_universe: UniverseSelection | None,
    latest_signals: list[TradingSignal],
    latest_executions: list[ExecutionResult],
) -> list[PortfolioCompositionEntry]:
    portfolio_value = portfolio.portfolio_value if portfolio.portfolio_value > 0 else 0.0
    candidate_by_symbol = {candidate.symbol: candidate for candidate in (latest_universe.candidates if latest_universe else [])}
    signal_by_symbol = {signal.symbol: signal for signal in latest_signals}
    execution_by_symbol = {execution.symbol: execution for execution in latest_executions if execution.status == "filled"}
    position_by_symbol = {position.symbol: position for position in portfolio.positions}
    symbols = set(position_by_symbol) | set(candidate_by_symbol) | set(signal_by_symbol)

    entries: list[PortfolioCompositionEntry] = []
    for symbol in sorted(symbols, key=lambda item: (item not in (latest_universe.selected_symbols if latest_universe else []), item)):
        position = position_by_symbol.get(symbol)
        candidate = candidate_by_symbol.get(symbol)
        signal = signal_by_symbol.get(symbol)
        execution = execution_by_symbol.get(symbol)
        market_value = position.market_value if position else 0.0
        actual_weight = (market_value / portfolio_value) if portfolio_value > 0 else 0.0
        target_weight = None
        if candidate is not None:
            target_weight = candidate.target_weight
        elif signal is not None:
            target_weight = signal.target_weight
        current_price = position.market_price if position else (candidate.latest_price if candidate else 0.0)
        mark_vs_fill_bps = None
        if execution and execution.price > 0 and current_price > 0:
            raw_bps = ((current_price - execution.price) / execution.price) * 10000
            mark_vs_fill_bps = raw_bps if execution.side == "buy" else -raw_bps

        entries.append(
            PortfolioCompositionEntry(
                symbol=symbol,
                kind="asset",
                quantity=position.quantity if position else 0.0,
                avg_entry_price=position.avg_entry_price if position else None,
                current_price=current_price,
                market_value=round(market_value, 2),
                unrealized_pnl=round(position.unrealized_pnl if position else 0.0, 2),
                actual_weight=round(actual_weight, 4),
                target_weight=round(target_weight, 4) if target_weight is not None else None,
                weight_gap=round((actual_weight - target_weight), 4) if target_weight is not None else None,
                exposure_state=signal.exposure_state if signal else None,
                category=candidate.category if candidate else None,
                selected_for_allocation=bool(candidate.selected) if candidate else bool(signal.selected_for_allocation) if signal else False,
                last_fill_price=execution.price if execution else None,
                mark_vs_last_fill_bps=round(mark_vs_fill_bps, 2) if mark_vs_fill_bps is not None else None,
            )
        )

    cash_weight = (portfolio.cash_usd / portfolio_value) if portfolio_value > 0 else 0.0
    entries.append(
        PortfolioCompositionEntry(
            symbol="CASH",
            kind="cash",
            quantity=None,
            avg_entry_price=None,
            current_price=1.0,
            market_value=round(portfolio.cash_usd, 2),
            unrealized_pnl=0.0,
            actual_weight=round(cash_weight, 4),
            target_weight=round(latest_universe.cash_reserve_weight, 4) if latest_universe else None,
            weight_gap=round(cash_weight - latest_universe.cash_reserve_weight, 4) if latest_universe else None,
            exposure_state="cash_reserve",
            category="cash",
            selected_for_allocation=True,
            last_fill_price=None,
            mark_vs_last_fill_bps=None,
        )
    )
    return entries


def _record_successful_history(
    *,
    started_at_ms: int,
    finished_at_ms: int,
    symbol_scope: str,
    interval_seconds: int,
    portfolio_source: str,
    result: TradingRunResponse,
) -> None:
    try:
        SqliteHistoryLedger().record_successful_cycle(
            started_at_ms=started_at_ms,
            finished_at_ms=finished_at_ms,
            symbol_scope=symbol_scope,
            market_source=result.market_snapshot.source,
            signal_engine_type=result.signal.engine_type,
            interval_seconds=interval_seconds,
            cycle_outcome=_cycle_outcome(result),
            universe=result.universe,
            signals=result.signals,
            risk_decisions=result.risk_decisions,
            executions=result.execution_results,
            portfolio=result.portfolio,
            portfolio_source=portfolio_source,
        )
    except Exception as exc:
        emit_event(
            level="WARNING",
            component="ledger",
            message="SQLite history write failed for successful cycle.",
            data={"pair": symbol_scope, "error": str(exc)},
        )


def _record_failed_history(
    *,
    started_at_ms: int,
    finished_at_ms: int,
    symbol_scope: str,
    interval_seconds: int,
    signal_engine_type: str,
    error_message: str,
) -> None:
    try:
        SqliteHistoryLedger().record_failed_cycle(
            started_at_ms=started_at_ms,
            finished_at_ms=finished_at_ms,
            symbol_scope=symbol_scope,
            market_source=get_settings().kraken_market_source,
            signal_engine_type=signal_engine_type,
            interval_seconds=interval_seconds,
            error_message=error_message,
        )
    except Exception as exc:
        emit_event(
            level="WARNING",
            component="ledger",
            message="SQLite history write failed for failed cycle.",
            data={"pair": symbol_scope, "error": str(exc)},
        )
