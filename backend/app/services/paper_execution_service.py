from __future__ import annotations

import time

from backend.app.core.config import get_settings
from backend.app.schemas.market import MarketSnapshot
from backend.app.schemas.trading import (
    ExecutionRequest,
    ExecutionResult,
    PnlState,
    PortfolioState,
    PositionState,
)


INVARIANT_TOLERANCE_USD = 0.05


class PortfolioInvariantError(RuntimeError):
    """Raised when paper portfolio accounting violates the cash-plus-positions invariant."""


def mark_portfolio_to_market(
    portfolio: PortfolioState,
    snapshot: MarketSnapshot | list[MarketSnapshot] | dict[str, MarketSnapshot],
) -> tuple[PortfolioState, PnlState]:
    snapshots_by_symbol = _snapshot_map(snapshot)
    updated_portfolio = _rebuild_portfolio(
        cash_usd=portfolio.cash_usd,
        positions=portfolio.positions,
        snapshots_by_symbol=snapshots_by_symbol,
        timestamp_ms=int(time.time() * 1000),
        realized_pnl=portfolio.realized_pnl,
    )
    return updated_portfolio, portfolio_to_pnl(updated_portfolio)


def execute_paper_request(
    request: ExecutionRequest,
    portfolio: PortfolioState,
    snapshot: MarketSnapshot,
    valuation_snapshot: MarketSnapshot | list[MarketSnapshot] | dict[str, MarketSnapshot] | None = None,
) -> tuple[ExecutionResult, PortfolioState, PnlState]:
    settings = get_settings()
    snapshots_by_symbol = _snapshot_map(valuation_snapshot or snapshot)
    snapshots_by_symbol[snapshot.pair] = snapshot
    portfolio, _ = mark_portfolio_to_market(portfolio, snapshots_by_symbol)
    timestamp_ms = int(time.time() * 1000)
    existing = _find_position(portfolio, request.symbol)
    current_weight = _current_weight(portfolio, request.symbol)

    if request.side == "hold":
        result = ExecutionResult(
            status="noop",
            mode="paper",
            symbol=request.symbol,
            side="hold",
            size=0.0,
            target_weight=request.target_weight,
            current_weight_before=round(current_weight, 4),
            current_weight_after=round(current_weight, 4),
            rebalance_gap=request.rebalance_gap,
            exposure_state=request.exposure_state,
            action_policy=request.action_policy,
            price=snapshot.last,
            quantity=0.0,
            notional_usd=0.0,
            timestamp_ms=timestamp_ms,
            reason=request.reason,
        )
        return result, portfolio, portfolio_to_pnl(portfolio)

    if request.side == "buy":
        desired_notional = portfolio.portfolio_value * request.target_weight
        current_notional = (existing.quantity * snapshot.last) if existing else 0.0
        trade_notional = min(max(desired_notional - current_notional, 0.0), portfolio.cash_usd)
        if trade_notional < settings.paper_min_trade_notional_usd:
            result = ExecutionResult(
                status="noop",
                mode="paper",
                symbol=request.symbol,
                side="buy",
                size=max(request.target_weight - current_weight, 0.0),
                target_weight=request.target_weight,
                current_weight_before=round(current_weight, 4),
                current_weight_after=round(current_weight, 4),
                rebalance_gap=request.rebalance_gap,
                exposure_state=request.exposure_state,
                action_policy=request.action_policy,
                price=snapshot.ask,
                quantity=0.0,
                notional_usd=0.0,
                timestamp_ms=timestamp_ms,
                reason="Requested paper rebalance was below the minimum notional threshold.",
            )
            return result, portfolio, portfolio_to_pnl(portfolio)

        quantity = trade_notional / snapshot.ask
        existing_quantity = existing.quantity if existing else 0.0
        new_quantity = existing_quantity + quantity
        total_cost = trade_notional + ((existing.avg_entry_price * existing_quantity) if existing else 0.0)
        avg_entry_price = total_cost / new_quantity
        positions = [position for position in portfolio.positions if position.symbol != request.symbol and position.quantity > 1e-8]
        positions.append(
            PositionState(
                symbol=request.symbol,
                quantity=round(new_quantity, 8),
                avg_entry_price=round(avg_entry_price, 2),
                market_price=snapshot.last,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=existing.realized_pnl if existing else 0.0,
            )
        )
        updated_portfolio = _rebuild_portfolio(
            cash_usd=portfolio.cash_usd - trade_notional,
            positions=positions,
            snapshots_by_symbol=snapshots_by_symbol,
            timestamp_ms=timestamp_ms,
            realized_pnl=portfolio.realized_pnl,
        )
        post_weight = _current_weight(updated_portfolio, request.symbol)
        result = ExecutionResult(
            status="filled",
            mode="paper",
            symbol=request.symbol,
            side="buy",
            size=max(request.target_weight - current_weight, 0.0),
            target_weight=request.target_weight,
            current_weight_before=round(current_weight, 4),
            current_weight_after=round(post_weight, 4),
            rebalance_gap=request.rebalance_gap,
            exposure_state=request.exposure_state,
            action_policy=request.action_policy,
            price=snapshot.ask,
            quantity=round(quantity, 8),
            notional_usd=round(trade_notional, 2),
            timestamp_ms=timestamp_ms,
            reason=request.reason,
        )
        return result, updated_portfolio, portfolio_to_pnl(updated_portfolio)

    if not existing or existing.quantity <= 0:
        result = ExecutionResult(
            status="noop",
            mode="paper",
            symbol=request.symbol,
            side="sell",
            size=0.0,
            target_weight=request.target_weight,
            current_weight_before=round(current_weight, 4),
            current_weight_after=round(current_weight, 4),
            rebalance_gap=request.rebalance_gap,
            exposure_state=request.exposure_state,
            action_policy=request.action_policy,
            price=snapshot.bid,
            quantity=0.0,
            notional_usd=0.0,
            timestamp_ms=timestamp_ms,
            reason="No paper position was open to sell.",
        )
        return result, portfolio, portfolio_to_pnl(portfolio)

    desired_notional = portfolio.portfolio_value * request.target_weight
    current_notional = existing.quantity * snapshot.last
    trade_notional = max(current_notional - desired_notional, 0.0)
    if trade_notional < settings.paper_min_trade_notional_usd and request.action_policy != "flatten":
        result = ExecutionResult(
            status="noop",
            mode="paper",
            symbol=request.symbol,
            side="sell",
            size=max(current_weight - request.target_weight, 0.0),
            target_weight=request.target_weight,
            current_weight_before=round(current_weight, 4),
            current_weight_after=round(current_weight, 4),
            rebalance_gap=request.rebalance_gap,
            exposure_state=request.exposure_state,
            action_policy=request.action_policy,
            price=snapshot.bid,
            quantity=0.0,
            notional_usd=0.0,
            timestamp_ms=timestamp_ms,
            reason="Requested paper reduction was below the minimum notional threshold.",
        )
        return result, portfolio, portfolio_to_pnl(portfolio)

    quantity = min(existing.quantity, trade_notional / snapshot.bid if snapshot.bid > 0 else existing.quantity)
    if request.action_policy == "flatten":
        quantity = existing.quantity
        trade_notional = current_notional
    proceeds = quantity * snapshot.bid
    realized_delta = (snapshot.bid - existing.avg_entry_price) * quantity
    remaining_quantity = max(existing.quantity - quantity, 0.0)
    positions = [position for position in portfolio.positions if position.symbol != request.symbol]
    if remaining_quantity > 1e-8 and request.target_weight > 0:
        remaining_position = PositionState(
            symbol=request.symbol,
            quantity=round(remaining_quantity, 8),
            avg_entry_price=existing.avg_entry_price,
            market_price=snapshot.last,
            market_value=0.0,
            unrealized_pnl=0.0,
            realized_pnl=round(existing.realized_pnl + realized_delta, 2),
        )
        positions.append(remaining_position)
    updated_portfolio = _rebuild_portfolio(
        cash_usd=portfolio.cash_usd + proceeds,
        positions=positions,
        snapshots_by_symbol=snapshots_by_symbol,
        timestamp_ms=timestamp_ms,
        realized_pnl=portfolio.realized_pnl + realized_delta,
    )
    post_weight = _current_weight(updated_portfolio, request.symbol)
    result = ExecutionResult(
        status="filled",
        mode="paper",
        symbol=request.symbol,
        side="sell",
        size=max(current_weight - request.target_weight, 0.0),
        target_weight=request.target_weight,
        current_weight_before=round(current_weight, 4),
        current_weight_after=round(post_weight, 4),
        rebalance_gap=request.rebalance_gap,
        exposure_state=request.exposure_state,
        action_policy=request.action_policy,
        price=snapshot.bid,
        quantity=round(quantity, 8),
        notional_usd=round(proceeds, 2),
        timestamp_ms=timestamp_ms,
        reason=request.reason,
    )
    return result, updated_portfolio, portfolio_to_pnl(updated_portfolio)


def portfolio_to_pnl(portfolio: PortfolioState) -> PnlState:
    timestamp_ms = int(time.time() * 1000)
    return PnlState(
        realized_pnl=round(portfolio.realized_pnl, 2),
        unrealized_pnl=round(portfolio.unrealized_pnl, 2),
        net_pnl=round(portfolio.realized_pnl + portfolio.unrealized_pnl, 2),
        timestamp_ms=timestamp_ms,
    )


def _current_weight(portfolio: PortfolioState, symbol: str) -> float:
    if portfolio.portfolio_value <= 0:
        return 0.0
    current_value = sum(position.quantity * position.market_price for position in portfolio.positions if position.symbol == symbol)
    return current_value / portfolio.portfolio_value


def _snapshot_map(snapshot: MarketSnapshot | list[MarketSnapshot] | dict[str, MarketSnapshot]) -> dict[str, MarketSnapshot]:
    if isinstance(snapshot, dict):
        return snapshot
    if isinstance(snapshot, list):
        return {item.pair: item for item in snapshot}
    return {snapshot.pair: snapshot}


def _find_position(portfolio: PortfolioState, symbol: str) -> PositionState | None:
    return next((position for position in portfolio.positions if position.symbol == symbol), None)


def _rebuild_portfolio(
    *,
    cash_usd: float,
    positions: list[PositionState],
    snapshots_by_symbol: dict[str, MarketSnapshot],
    timestamp_ms: int,
    realized_pnl: float,
) -> PortfolioState:
    canonical_positions: list[PositionState] = []
    unrealized_pnl = 0.0

    for position in positions:
        if position.quantity <= 1e-8:
            continue
        market_snapshot = snapshots_by_symbol.get(position.symbol)
        market_price = market_snapshot.last if market_snapshot else position.market_price
        market_value = position.quantity * market_price
        position_unrealized = (market_price - position.avg_entry_price) * position.quantity
        unrealized_pnl += position_unrealized
        canonical_positions.append(
            PositionState(
                symbol=position.symbol,
                quantity=round(position.quantity, 8),
                avg_entry_price=round(position.avg_entry_price, 2),
                market_price=round(market_price, 8),
                market_value=round(market_value, 2),
                unrealized_pnl=round(position_unrealized, 2),
                realized_pnl=round(position.realized_pnl, 2),
            )
        )

    portfolio = PortfolioState(
        cash_usd=round(cash_usd, 2),
        positions=canonical_positions,
        portfolio_value=round(cash_usd + sum(position.market_value for position in canonical_positions), 2),
        realized_pnl=round(realized_pnl, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        timestamp_ms=timestamp_ms,
    )
    _assert_portfolio_invariant(portfolio)
    return portfolio


def _assert_portfolio_invariant(portfolio: PortfolioState) -> None:
    expected_value = round(portfolio.cash_usd + sum(position.quantity * position.market_price for position in portfolio.positions), 2)
    actual_value = round(portfolio.portfolio_value, 2)
    if abs(expected_value - actual_value) > INVARIANT_TOLERANCE_USD:
        raise PortfolioInvariantError(
            "Portfolio invariant violated: "
            f"portfolio_value={actual_value} expected={expected_value} "
            f"cash_usd={round(portfolio.cash_usd, 2)}"
        )
