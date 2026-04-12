from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.schemas.trading import (
    ExecutionRequest,
    ExecutionResult,
    PnlState,
    PortfolioState,
    RiskDecision,
    TradingRunResponse,
    TradingSignal,
    TradingStatusResponse,
    UniverseSelection,
)
from backend.app.services.event_log import emit_event
from backend.app.services.paper_execution_service import (
    PortfolioInvariantError,
    execute_paper_request,
    mark_portfolio_to_market,
    portfolio_to_pnl,
)
from backend.app.services.risk_service import evaluate_risk
from backend.app.services.signal_service import generate_signal
from backend.app.services.state_store import JsonStateStore
from backend.app.services.universe_service import REFERENCE_SYMBOL, build_universe_selection, scan_candidate_universe


def get_trading_status(pair: str) -> TradingStatusResponse:
    settings = get_settings()
    store = JsonStateStore()
    latest_snapshots = store.load_market_snapshots()
    portfolio = store.load_portfolio()
    if latest_snapshots:
        portfolio, pnl = mark_portfolio_to_market(portfolio, latest_snapshots)
        store.save_portfolio(portfolio)
    else:
        pnl = portfolio_to_pnl(portfolio)

    latest_signals = store.load_signals()
    latest_risk_decisions = store.load_risk_decisions()
    latest_executions = store.load_executions()
    return TradingStatusResponse(
        pair=pair,
        market_source=settings.kraken_market_source,
        execution_mode="paper",
        latest_universe=store.load_universe(),
        latest_signals=latest_signals,
        latest_risk_decisions=latest_risk_decisions,
        latest_executions=latest_executions,
        latest_signal=latest_signals[0] if latest_signals else None,
        latest_risk_decision=latest_risk_decisions[0] if latest_risk_decisions else None,
        latest_execution=latest_executions[0] if latest_executions else None,
        portfolio=portfolio,
        pnl=pnl,
    )


def run_trading_cycle(pair: str, trigger: str = "manual") -> TradingRunResponse:
    store = JsonStateStore()
    contexts = scan_candidate_universe()
    snapshots = [context.snapshot for context in contexts]
    snapshot_by_symbol = {snapshot.pair: snapshot for snapshot in snapshots}
    primary_snapshot = snapshot_by_symbol.get(pair) or snapshot_by_symbol.get(REFERENCE_SYMBOL) or snapshots[0]
    store.save_market_snapshots(snapshots)
    store.save_market_snapshot(primary_snapshot)

    raw_signals = [generate_signal(context.bundle) for context in contexts]
    universe, signals = build_universe_selection(contexts=contexts, raw_signals=raw_signals)
    store.save_universe(universe)
    store.save_signals(signals)
    emit_event(
        level="INFO",
        component="universe",
        message="Universe selection updated.",
        data={
            "selected_symbols": ",".join(universe.selected_symbols) or "none",
            "gross_target_weight": universe.gross_target_weight,
            "cash_reserve_weight": universe.cash_reserve_weight,
            "trigger": trigger,
        },
    )

    portfolio = store.load_portfolio()
    portfolio, _ = mark_portfolio_to_market(portfolio, snapshots)
    held_symbols = {position.symbol for position in portfolio.positions}
    latest_execution_by_symbol = _latest_execution_by_symbol(store.load_executions())
    signal_by_symbol = {signal.symbol: signal for signal in signals}
    ordered_symbols = _ordered_trade_symbols(signals, universe, held_symbols)

    risk_decisions: list[RiskDecision] = []
    execution_requests: list[ExecutionRequest] = []
    execution_results: list[ExecutionResult] = []

    for symbol in ordered_symbols:
        signal = signal_by_symbol[symbol]
        snapshot = snapshot_by_symbol[symbol]
        latest_symbol_execution = latest_execution_by_symbol.get(symbol)
        risk_decision = evaluate_risk(signal, snapshot, portfolio, latest_symbol_execution)
        risk_decisions.append(risk_decision)
        emit_event(
            level="INFO" if risk_decision.approved else "WARNING",
            component="risk",
            message="Risk gate evaluated portfolio signal.",
            data={
                "pair": signal.symbol,
                "approved": risk_decision.approved,
                "side": risk_decision.side,
                "action_policy": risk_decision.action_policy,
                "target_weight": risk_decision.target_weight,
                "current_weight": risk_decision.current_weight,
                "rebalance_gap": risk_decision.rebalance_gap,
                "reason": risk_decision.reason,
                "trigger": trigger,
            },
        )

        execution_request = ExecutionRequest(
            mode="paper",
            symbol=signal.symbol,
            side=risk_decision.side,
            target_weight=risk_decision.target_weight if risk_decision.approved else risk_decision.current_weight,
            current_weight=risk_decision.current_weight,
            rebalance_gap=risk_decision.rebalance_gap,
            exposure_state=risk_decision.exposure_state,
            action_policy=risk_decision.action_policy,
            confidence=signal.confidence,
            requested_at_ms=risk_decision.timestamp_ms,
            reason=risk_decision.reason,
        )
        execution_requests.append(execution_request)
        execution_result, portfolio, _ = execute_paper_request(
            execution_request,
            portfolio,
            snapshot,
            snapshot_by_symbol,
        )
        execution_results.append(execution_result)
        latest_execution_by_symbol[symbol] = execution_result
        emit_event(
            level="INFO" if execution_result.status == "filled" else "WARNING",
            component="execution",
            message="Paper execution processed.",
            data={
                "pair": execution_result.symbol,
                "status": execution_result.status,
                "side": execution_result.side,
                "action_policy": execution_result.action_policy,
                "target_weight": execution_result.target_weight,
                "current_weight_before": execution_result.current_weight_before,
                "current_weight_after": execution_result.current_weight_after,
                "reason": execution_result.reason,
                "mode": execution_result.mode,
                "trigger": trigger,
            },
        )

    try:
        portfolio, _ = mark_portfolio_to_market(portfolio, snapshot_by_symbol)
    except PortfolioInvariantError:
        emit_event(
            level="ERROR",
            component="portfolio",
            message="Portfolio invariant check failed after the cycle.",
            data={"trigger": trigger},
        )
        raise

    store.save_risk_decisions(risk_decisions)
    store.save_executions(execution_results)
    store.save_portfolio(portfolio)
    pnl = portfolio_to_pnl(portfolio)

    emit_event(
        level="INFO",
        component="portfolio",
        message="Paper portfolio updated.",
        data={
            "portfolio_value": portfolio.portfolio_value,
            "cash_usd": portfolio.cash_usd,
            "realized_pnl": portfolio.realized_pnl,
            "unrealized_pnl": portfolio.unrealized_pnl,
            "selected_symbols": ",".join(universe.selected_symbols) or "none",
        },
    )

    primary_signal = _primary_signal(signals)
    primary_risk = _find_for_symbol(risk_decisions, primary_signal.symbol)
    primary_execution_request = _find_request_for_symbol(execution_requests, primary_signal.symbol)
    primary_execution_result = _find_execution_for_symbol(execution_results, primary_signal.symbol)
    return TradingRunResponse(
        pair=pair,
        market_snapshot=primary_snapshot,
        universe=universe,
        market_snapshots=snapshots,
        signals=signals,
        risk_decisions=risk_decisions,
        execution_requests=execution_requests,
        execution_results=execution_results,
        signal=primary_signal,
        risk_decision=primary_risk,
        execution_request=primary_execution_request,
        execution_result=primary_execution_result,
        portfolio=portfolio,
        pnl=pnl,
    )


def _ordered_trade_symbols(
    signals: list[TradingSignal],
    universe: UniverseSelection,
    held_symbols: set[str],
) -> list[str]:
    order: list[str] = []
    signal_rank = [signal.symbol for signal in signals if signal.selected_for_allocation]
    for symbol in signal_rank + list(held_symbols):
        if symbol not in order:
            order.append(symbol)
    if not order and signals:
        order.append(signals[0].symbol)
    return order


def _latest_execution_by_symbol(executions: list[ExecutionResult]) -> dict[str, ExecutionResult]:
    latest: dict[str, ExecutionResult] = {}
    for execution in executions:
        latest.setdefault(execution.symbol, execution)
    return latest


def _primary_signal(signals: list[TradingSignal]) -> TradingSignal:
    selected = next((signal for signal in signals if signal.selected_for_allocation), None)
    if selected is not None:
        return selected
    return signals[0]


def _find_for_symbol(decisions: list[RiskDecision], symbol: str) -> RiskDecision:
    for decision in decisions:
        if decision.symbol == symbol:
            return decision
    return decisions[0]


def _find_request_for_symbol(requests: list[ExecutionRequest], symbol: str) -> ExecutionRequest:
    for request in requests:
        if request.symbol == symbol:
            return request
    return requests[0]


def _find_execution_for_symbol(executions: list[ExecutionResult], symbol: str) -> ExecutionResult:
    for execution in executions:
        if execution.symbol == symbol:
            return execution
    return executions[0]
