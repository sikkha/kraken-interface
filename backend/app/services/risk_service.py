from __future__ import annotations

import time

from backend.app.core.config import get_settings
from backend.app.schemas.market import MarketSnapshot
from backend.app.schemas.trading import ExecutionResult, PortfolioState, RiskDecision, TradingSignal


def evaluate_risk(
    signal: TradingSignal,
    snapshot: MarketSnapshot,
    portfolio: PortfolioState,
    latest_execution: ExecutionResult | None,
) -> RiskDecision:
    settings = get_settings()
    timestamp_ms = int(time.time() * 1000)
    current_position_value = sum(
        position.quantity * position.market_price for position in portfolio.positions if position.symbol == signal.symbol
    )
    current_weight = current_position_value / portfolio.portfolio_value if portfolio.portfolio_value > 0 else 0.0
    target_weight = min(signal.target_weight, settings.max_position_weight)
    rebalance_gap = target_weight - current_weight
    spread_bps = (snapshot.spread / snapshot.mid) * 10000 if snapshot.mid > 0 else 0.0
    cooldown_remaining = 0
    if latest_execution and latest_execution.status == "filled":
        cooldown_remaining = max(
            0,
            latest_execution.timestamp_ms + (settings.trade_cooldown_seconds * 1000) - timestamp_ms,
        )

    action_policy = _action_policy(target_weight, current_weight, settings.rebalance_deadband_weight)
    checks: dict[str, object] = {
        "signal": signal.signal,
        "confidence": signal.confidence,
        "regime_score": signal.regime_score,
        "target_weight": round(target_weight, 4),
        "current_weight": round(current_weight, 4),
        "rebalance_gap": round(rebalance_gap, 4),
        "spread_bps": round(spread_bps, 2),
        "cooldown_remaining_ms": cooldown_remaining,
        "cooldown_active": cooldown_remaining > 0,
        "rolling_volatility": round(signal.features_summary.rolling_volatility, 6),
        "volatility_flag": signal.features_summary.rolling_volatility > settings.abnormal_volatility_threshold,
        "exposure_state": signal.exposure_state,
        "action_policy": action_policy,
    }

    if action_policy == "hold":
        return _decision(
            symbol=signal.symbol,
            approved=False,
            side="hold",
            size=0.0,
            target_weight=target_weight,
            current_weight=current_weight,
            rebalance_gap=rebalance_gap,
            exposure_state=signal.exposure_state,
            action_policy=action_policy,
            reason="Rebalance gap is inside the configured deadband, so the paper portfolio holds.",
            timestamp_ms=timestamp_ms,
            checks=checks,
        )

    if spread_bps > settings.max_spread_bps:
        return _decision(
            symbol=signal.symbol,
            approved=False,
            side="hold",
            size=0.0,
            target_weight=target_weight,
            current_weight=current_weight,
            rebalance_gap=rebalance_gap,
            exposure_state=signal.exposure_state,
            action_policy=action_policy,
            reason="Spread exceeds the configured limit for this rebalance.",
            timestamp_ms=timestamp_ms,
            checks=checks,
        )

    if action_policy == "increase":
        if signal.confidence < settings.signal_confidence_threshold:
            return _decision(
                symbol=signal.symbol,
                approved=False,
                side="hold",
                size=0.0,
                target_weight=target_weight,
                current_weight=current_weight,
                rebalance_gap=rebalance_gap,
                exposure_state=signal.exposure_state,
                action_policy=action_policy,
                reason="Increase request is below the configured confidence threshold.",
                timestamp_ms=timestamp_ms,
                checks=checks,
            )

        if cooldown_remaining > 0:
            return _decision(
                symbol=signal.symbol,
                approved=False,
                side="hold",
                size=0.0,
                target_weight=target_weight,
                current_weight=current_weight,
                rebalance_gap=rebalance_gap,
                exposure_state=signal.exposure_state,
                action_policy=action_policy,
                reason="Cooldown is still active from the last filled trade.",
                timestamp_ms=timestamp_ms,
                checks=checks,
            )

        if signal.features_summary.rolling_volatility > settings.abnormal_volatility_threshold:
            return _decision(
                symbol=signal.symbol,
                approved=False,
                side="hold",
                size=0.0,
                target_weight=target_weight,
                current_weight=current_weight,
                rebalance_gap=rebalance_gap,
                exposure_state=signal.exposure_state,
                action_policy=action_policy,
                reason="Volatility placeholder hook blocked the exposure increase.",
                timestamp_ms=timestamp_ms,
                checks=checks,
            )

        return _decision(
            symbol=signal.symbol,
            approved=True,
            side="buy",
            size=abs(rebalance_gap),
            target_weight=target_weight,
            current_weight=current_weight,
            rebalance_gap=rebalance_gap,
            exposure_state=signal.exposure_state,
            action_policy=action_policy,
            reason="Exposure should increase toward the new target weight.",
            timestamp_ms=timestamp_ms,
            checks=checks,
        )

    if not portfolio.positions:
        return _decision(
            symbol=signal.symbol,
            approved=False,
            side="hold",
            size=0.0,
            target_weight=target_weight,
            current_weight=current_weight,
            rebalance_gap=rebalance_gap,
            exposure_state=signal.exposure_state,
            action_policy=action_policy,
            reason="No paper position is open to reduce from the current target.",
            timestamp_ms=timestamp_ms,
            checks=checks,
        )

    reason = (
        f"Target exposure dropped to flat, so the paper engine will flatten the {signal.symbol} position."
        if action_policy == "flatten"
        else f"Target exposure fell materially below the current {signal.symbol} weight, so the paper engine will reduce."
    )
    return _decision(
        symbol=signal.symbol,
        approved=True,
        side="sell",
        size=abs(rebalance_gap),
        target_weight=target_weight,
        current_weight=current_weight,
        rebalance_gap=rebalance_gap,
        exposure_state=signal.exposure_state,
        action_policy=action_policy,
        reason=reason,
        timestamp_ms=timestamp_ms,
        checks=checks,
    )


def _action_policy(target_weight: float, current_weight: float, deadband: float) -> str:
    gap = target_weight - current_weight
    if gap > deadband:
        return "increase"
    if gap < -deadband:
        if target_weight <= deadband / 2:
            return "flatten"
        return "reduce"
    return "hold"


def _decision(
    *,
    symbol: str,
    approved: bool,
    side: str,
    size: float,
    target_weight: float,
    current_weight: float,
    rebalance_gap: float,
    exposure_state: str,
    action_policy: str,
    reason: str,
    timestamp_ms: int,
    checks: dict[str, object],
) -> RiskDecision:
    return RiskDecision(
        symbol=symbol,
        approved=approved,
        side=side,
        size=round(size, 4),
        target_weight=round(target_weight, 4),
        current_weight=round(current_weight, 4),
        rebalance_gap=round(rebalance_gap, 4),
        exposure_state=exposure_state,
        action_policy=action_policy,
        reason=reason,
        timestamp_ms=timestamp_ms,
        checks=checks,
    )
