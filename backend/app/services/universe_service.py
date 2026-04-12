from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from backend.app.adapters.kraken_market import KrakenMarketAdapter, KrakenMarketReadError
from backend.app.core.config import get_settings
from backend.app.schemas.market import MarketCandlesResponse, MarketSnapshot
from backend.app.schemas.trading import (
    AssetClassAllocation,
    TradingSignal,
    UniverseCandidate,
    UniverseSelection,
)
from backend.app.services.event_log import emit_event
from backend.app.services.feature_service import FeatureBundle, build_feature_bundle


REFERENCE_SYMBOL = "BTCUSD"
UNIVERSE_VOLUME_WINDOW = 24
UNIVERSE_RETURN_WINDOW = 48
CLASS_RETURN_WINDOW = 96
CLASS_DRAWNDOWN_WINDOW = 120
CLASS_MIN_CASH_FLOOR = 0.15


@dataclass(frozen=True)
class AssetClassSpec:
    class_id: str
    label: str
    members: tuple[str, ...]
    live_market_data: bool
    allocation_enabled: bool
    max_weight: float
    max_selected_assets: int
    description: str


@dataclass(frozen=True)
class UniverseMarketContext:
    symbol: str
    snapshot: MarketSnapshot
    candles: MarketCandlesResponse
    bundle: FeatureBundle
    source: str
    used_fallback: bool = False


ASSET_CLASS_SPECS: tuple[AssetClassSpec, ...] = (
    AssetClassSpec(
        class_id="cash_stable",
        label="Cash / Stablecoins",
        members=("CASH", "USDC", "USDT"),
        live_market_data=False,
        allocation_enabled=True,
        max_weight=1.0,
        max_selected_assets=0,
        description="Active reserve bucket. CASH is live in paper accounting; stablecoin rotation is scaffolded.",
    ),
    AssetClassSpec(
        class_id="crypto_majors",
        label="Crypto Majors",
        members=("BTCUSD", "ETHUSD"),
        live_market_data=True,
        allocation_enabled=True,
        max_weight=0.45,
        max_selected_assets=2,
        description="Live Kraken spot majors with the best liquidity and structural trend quality.",
    ),
    AssetClassSpec(
        class_id="crypto_speculative",
        label="Crypto Speculative",
        members=("SOLUSD", "ADAUSD", "AVAXUSD"),
        live_market_data=True,
        allocation_enabled=True,
        max_weight=0.20,
        max_selected_assets=1,
        description="Higher-beta live crypto sleeve capped below majors.",
    ),
    AssetClassSpec(
        class_id="equity_xstocks",
        label="Equity / xStocks",
        members=("NVDAx", "MSFTx", "AAPLx"),
        live_market_data=False,
        allocation_enabled=False,
        max_weight=0.30,
        max_selected_assets=0,
        description="Architectural scaffold only in this milestone. Not wired into the live Kraken spot execution path.",
    ),
    AssetClassSpec(
        class_id="gold_tokens",
        label="Gold-Backed Tokens",
        members=("PAXG", "XAUT"),
        live_market_data=False,
        allocation_enabled=False,
        max_weight=0.15,
        max_selected_assets=0,
        description="Research/scaffolded sleeve. Not wired into the live execution path yet.",
    ),
)

CLASS_SPEC_BY_ID = {spec.class_id: spec for spec in ASSET_CLASS_SPECS}
SYMBOL_TO_CLASS = {
    symbol: spec
    for spec in ASSET_CLASS_SPECS
    for symbol in spec.members
    if symbol != "CASH"
}
LIVE_CANDIDATE_UNIVERSE = [
    symbol
    for spec in ASSET_CLASS_SPECS
    if spec.live_market_data
    for symbol in spec.members
]


def candidate_universe() -> list[str]:
    return list(LIVE_CANDIDATE_UNIVERSE)


def scan_candidate_universe() -> list[UniverseMarketContext]:
    settings = get_settings()
    adapter = KrakenMarketAdapter(source_mode=settings.kraken_market_source)
    contexts: list[UniverseMarketContext] = []
    fallback_symbols: list[str] = []
    for symbol in candidate_universe():
        try:
            snapshot_payload = adapter.get_snapshot(symbol)
            candles_payload = adapter.get_candles(
                pair=symbol,
                interval=settings.signal_candle_interval,
                limit=settings.signal_candle_limit,
            )
            used_fallback = False
        except KrakenMarketReadError:
            snapshot_payload = adapter.fallback_snapshot(symbol)
            candles_payload = adapter.fallback_candles(
                pair=symbol,
                interval=settings.signal_candle_interval,
                limit=settings.signal_candle_limit,
            )
            used_fallback = True
            fallback_symbols.append(symbol)

        snapshot = MarketSnapshot.model_validate(snapshot_payload).model_copy(update={"pair": symbol})
        candles = MarketCandlesResponse.model_validate(candles_payload).model_copy(update={"pair": symbol})
        contexts.append(
            UniverseMarketContext(
                symbol=symbol,
                snapshot=snapshot,
                candles=candles,
                bundle=build_feature_bundle(candles),
                source="mock" if used_fallback else snapshot.source,
                used_fallback=used_fallback,
            )
        )

    emit_event(
        level="INFO" if not fallback_symbols else "WARNING",
        component="universe",
        message="Hierarchical universe scan completed.",
        data={
            "candidate_count": len(contexts),
            "selected_source": settings.kraken_market_source,
            "fallback_symbols": ",".join(fallback_symbols) if fallback_symbols else "none",
        },
    )
    return contexts


def build_universe_selection(
    *,
    contexts: list[UniverseMarketContext],
    raw_signals: list[TradingSignal],
) -> tuple[UniverseSelection, list[TradingSignal]]:
    settings = get_settings()
    timestamp_ms = int(time.time() * 1000)
    signal_map = {signal.symbol: signal for signal in raw_signals}
    context_map = {context.symbol: context for context in contexts}
    reference_rows = context_map.get(REFERENCE_SYMBOL).bundle.rows if REFERENCE_SYMBOL in context_map else []
    liquidity_scale = max((_average_dollar_volume(context.bundle) for context in contexts), default=1.0)

    candidates: list[UniverseCandidate] = []
    candidate_by_symbol: dict[str, UniverseCandidate] = {}
    for symbol in candidate_universe():
        context = context_map[symbol]
        signal = signal_map[symbol]
        spec = SYMBOL_TO_CLASS[symbol]
        realized_volatility = _realized_volatility(context.bundle)
        average_dollar_volume = _average_dollar_volume(context.bundle)
        beta_to_btc = _beta_to_reference(context.bundle, reference_rows)
        trend_quality = _trend_quality(context.bundle)
        volatility_score = _volatility_score(realized_volatility)
        liquidity_score = _clamp(average_dollar_volume / max(liquidity_scale, 1.0), 0.0, 1.0)
        beta_score = _clamp(beta_to_btc / 2.0, 0.0, 1.0)
        trend_quality_score = _clamp(trend_quality, 0.0, 1.0)
        regime_alignment_score = _clamp((signal.regime_score + 1.0) / 2.0, 0.0, 1.0)
        source_penalty = 0.1 if context.used_fallback else 0.0
        combined_universe_score = _clamp(
            (0.35 * regime_alignment_score)
            + (0.25 * liquidity_score)
            + (0.15 * volatility_score)
            + (0.15 * trend_quality_score)
            + (0.10 * beta_score)
            - source_penalty,
            0.0,
            1.0,
        )
        candidate = UniverseCandidate(
            symbol=symbol,
            asset_class=spec.class_id,
            asset_class_label=spec.label,
            live_tradeable=True,
            allocation_enabled=spec.allocation_enabled,
            source=context.source,
            latest_price=context.snapshot.last,
            realized_volatility=round(realized_volatility, 6),
            average_dollar_volume=round(average_dollar_volume, 2),
            beta_to_btc=round(beta_to_btc, 4),
            trend_quality=round(trend_quality, 4),
            volatility_score=round(volatility_score, 4),
            liquidity_score=round(liquidity_score, 4),
            beta_score=round(beta_score, 4),
            trend_quality_score=round(trend_quality_score, 4),
            regime_alignment_score=round(regime_alignment_score, 4),
            combined_universe_score=round(combined_universe_score, 4),
            category=_category_label(
                asset_class=spec.class_id,
                liquidity_score=liquidity_score,
                beta_to_btc=beta_to_btc,
                trend_quality=trend_quality,
                combined_score=combined_universe_score,
            ),
            base_target_weight=signal.base_target_weight,
            target_weight=0.0,
            selected=False,
            selected_within_class=False,
            selection_rank=None,
            note="live-compatible fallback was used for this symbol." if context.used_fallback else "",
        )
        candidates.append(candidate)
        candidate_by_symbol[symbol] = candidate

    class_allocations = _build_class_allocations(
        contexts=contexts,
        raw_signals=raw_signals,
        reference_rows=reference_rows,
    )
    target_by_symbol, rank_lookup, selected_symbols = _allocate_within_classes(
        class_allocations=class_allocations,
        candidates=candidates,
        signal_map=signal_map,
        settings=settings,
    )
    selected_classes = [
        allocation.class_id
        for allocation in class_allocations
        if allocation.target_weight > 0.0001
    ]

    updated_candidates: list[UniverseCandidate] = []
    updated_signals: list[TradingSignal] = []
    class_map = {allocation.class_id: allocation for allocation in class_allocations}
    for candidate in candidates:
        signal = signal_map[candidate.symbol]
        class_allocation = class_map[candidate.asset_class]
        final_target = target_by_symbol.get(candidate.symbol, 0.0)
        selected_for_allocation = final_target > 0.0
        updated_candidate = candidate.model_copy(
            update={
                "target_weight": round(final_target, 4),
                "class_score": round(class_allocation.class_score, 4),
                "class_confidence": round(class_allocation.class_confidence, 4),
                "class_target_weight": round(class_allocation.target_weight, 4),
                "selected": candidate.symbol in selected_symbols,
                "selected_within_class": candidate.symbol in class_allocation.selected_symbols,
                "selection_rank": rank_lookup.get(candidate.symbol),
                "note": candidate.note or _candidate_note(class_allocation, final_target),
            }
        )
        updated_candidates.append(updated_candidate)
        updated_signals.append(
            signal.model_copy(
                update={
                    "asset_class": candidate.asset_class,
                    "asset_class_label": candidate.asset_class_label,
                    "class_score": round(class_allocation.class_score, 4),
                    "class_confidence": round(class_allocation.class_confidence, 4),
                    "class_target_weight": round(class_allocation.target_weight, 4),
                    "live_tradeable": candidate.live_tradeable,
                    "target_weight": round(final_target, 4),
                    "universe_score": candidate.combined_universe_score,
                    "universe_category": candidate.category,
                    "selection_rank": rank_lookup.get(candidate.symbol),
                    "selected_for_allocation": selected_for_allocation,
                    "action_policy_reason": _portfolio_policy_reason(
                        signal=signal,
                        candidate=updated_candidate,
                        class_allocation=class_allocation,
                    ),
                }
            )
        )

    for spec in ASSET_CLASS_SPECS:
        if spec.live_market_data:
            continue
        class_allocation = class_map[spec.class_id]
        for symbol in spec.members:
            if symbol == "CASH":
                continue
            updated_candidates.append(
                UniverseCandidate(
                    symbol=symbol,
                    asset_class=spec.class_id,
                    asset_class_label=spec.label,
                    live_tradeable=False,
                    allocation_enabled=spec.allocation_enabled,
                    source="scaffold",
                    latest_price=0.0,
                    class_score=round(class_allocation.class_score, 4),
                    class_confidence=round(class_allocation.class_confidence, 4),
                    class_target_weight=round(class_allocation.target_weight, 4),
                    category="scaffolded",
                    note=spec.description,
                )
            )

    deployed_weight = round(sum(target_by_symbol.values()), 6)
    cash_weight = max(0.0, 1.0 - deployed_weight)
    selection = UniverseSelection(
        timestamp_ms=timestamp_ms,
        reference_symbol=REFERENCE_SYMBOL,
        candidate_symbols=[
            symbol
            for spec in ASSET_CLASS_SPECS
            for symbol in spec.members
            if symbol != "CASH"
        ],
        selected_classes=selected_classes,
        selected_symbols=[symbol for symbol in selected_symbols if target_by_symbol.get(symbol, 0.0) > 0],
        selected_count=len([symbol for symbol in selected_symbols if target_by_symbol.get(symbol, 0.0) > 0]),
        max_selected_assets=settings.portfolio_max_selected_assets,
        gross_target_weight=round(deployed_weight, 4),
        cash_reserve_weight=round(cash_weight, 4),
        selection_reason=(
            "The hierarchical allocator first scores asset classes with slower structural metrics, assigns class "
            "weights under explicit caps, and then lets the packaged GRU tactical engine choose the best live "
            "assets inside approved classes. Cash remains an active class decision."
        ),
        class_allocations=sorted(class_allocations, key=lambda allocation: allocation.target_weight, reverse=True),
        candidates=sorted(
            updated_candidates,
            key=lambda candidate: (
                candidate.live_tradeable,
                candidate.class_target_weight,
                candidate.target_weight,
                candidate.combined_universe_score,
            ),
            reverse=True,
        ),
    )
    return selection, sorted(
        updated_signals,
        key=lambda signal: (signal.class_target_weight, signal.target_weight, signal.universe_score),
        reverse=True,
    )


def _build_class_allocations(
    *,
    contexts: list[UniverseMarketContext],
    raw_signals: list[TradingSignal],
    reference_rows,
) -> list[AssetClassAllocation]:
    settings = get_settings()
    context_map = {context.symbol: context for context in contexts}
    signal_map = {signal.symbol: signal for signal in raw_signals}
    allocations: list[AssetClassAllocation] = []

    structural_risk_inputs: list[tuple[float, float]] = []
    for spec in ASSET_CLASS_SPECS:
        if spec.class_id == "cash_stable":
            continue
        live_members = [symbol for symbol in spec.members if symbol in context_map]
        if not live_members:
            allocations.append(
                AssetClassAllocation(
                    class_id=spec.class_id,
                    label=spec.label,
                    members=list(spec.members),
                    selected_symbols=[],
                    live_tradeable=spec.live_market_data,
                    allocation_enabled=spec.allocation_enabled,
                    class_score=0.0,
                    class_confidence=0.0,
                    target_weight=0.0,
                    category="scaffolded" if not spec.live_market_data else "inactive",
                    note=spec.description,
                )
            )
            continue

        trend = _class_trend([context_map[symbol].bundle for symbol in live_members])
        volatility = float(np.mean([_realized_volatility(context_map[symbol].bundle) for symbol in live_members]))
        rel_strength = _class_relative_strength(
            [context_map[symbol].bundle for symbol in live_members],
            reference_rows,
        )
        drawdown = _class_drawdown([context_map[symbol].bundle for symbol in live_members])
        mean_confidence = float(np.mean([signal_map[symbol].confidence for symbol in live_members]))
        confidence_stability = float(
            np.mean([signal_map[symbol].features_summary.persistence_ratio for symbol in live_members])
        )
        class_score = _class_score(
            trend=trend,
            volatility=volatility,
            rel_strength=rel_strength,
            drawdown=drawdown,
        )
        class_confidence = _class_confidence(
            mean_confidence=mean_confidence,
            confidence_stability=confidence_stability,
            class_score=class_score,
        )
        structural_risk_inputs.append((class_score, class_confidence))
        allocations.append(
            AssetClassAllocation(
                class_id=spec.class_id,
                label=spec.label,
                members=list(spec.members),
                selected_symbols=[],
                live_tradeable=spec.live_market_data,
                allocation_enabled=spec.allocation_enabled,
                class_score=round(class_score, 4),
                class_confidence=round(class_confidence, 4),
                target_weight=0.0,
                average_trend=round(trend, 4),
                average_realized_volatility=round(volatility, 6),
                relative_strength=round(rel_strength, 4),
                drawdown=round(drawdown, 4),
                confidence_stability=round(confidence_stability, 4),
                category=_class_category(spec.class_id, class_score, class_confidence),
                note=spec.description,
            )
        )

    cash_score, cash_confidence, cash_note = _cash_class_signal(structural_risk_inputs)
    allocations.insert(
        0,
        AssetClassAllocation(
            class_id="cash_stable",
            label=CLASS_SPEC_BY_ID["cash_stable"].label,
            members=list(CLASS_SPEC_BY_ID["cash_stable"].members),
            selected_symbols=["CASH"] if cash_score > -0.5 else [],
            live_tradeable=True,
            allocation_enabled=True,
            class_score=round(cash_score, 4),
            class_confidence=round(cash_confidence, 4),
            target_weight=1.0,
            average_trend=0.0,
            average_realized_volatility=0.0,
            relative_strength=0.0,
            drawdown=0.0,
            confidence_stability=round(cash_confidence, 4),
            category="defensive_reserve",
            note=cash_note,
        ),
    )

    raw_class_weights: dict[str, float] = {}
    active_allocations = [
        allocation for allocation in allocations
        if allocation.class_id != "cash_stable" and allocation.allocation_enabled and allocation.live_tradeable
    ]
    risk_aversion = float(np.mean([max(-allocation.class_score, 0.0) for allocation in active_allocations])) if active_allocations else 1.0
    uncertainty = 1.0 - float(np.mean([allocation.class_confidence for allocation in active_allocations])) if active_allocations else 1.0
    cash_floor = _clamp(CLASS_MIN_CASH_FLOOR + (0.20 * risk_aversion) + (0.15 * uncertainty), CLASS_MIN_CASH_FLOOR, 0.80)

    for allocation in active_allocations:
        positive_score = _clamp(
            (allocation.class_score - (-0.15)) / max(1.0 - (-0.15), 1e-4),
            0.0,
            1.0,
        )
        raw_class_weights[allocation.class_id] = positive_score * (0.45 + (0.55 * allocation.class_confidence))

    total_raw = sum(raw_class_weights.values())
    remaining_after_cash_floor = max(0.0, 1.0 - cash_floor)
    allocated_non_cash = 0.0
    updated_allocations: list[AssetClassAllocation] = []
    for allocation in allocations:
        spec = CLASS_SPEC_BY_ID[allocation.class_id]
        if allocation.class_id == "cash_stable":
            updated_allocations.append(allocation)
            continue
        if not allocation.allocation_enabled or not allocation.live_tradeable or total_raw <= 0:
            updated_allocations.append(allocation.model_copy(update={"target_weight": 0.0}))
            continue

        class_target = remaining_after_cash_floor * (raw_class_weights[allocation.class_id] / total_raw)
        class_target = _clamp(class_target, 0.0, spec.max_weight)
        allocated_non_cash += class_target
        updated_allocations.append(allocation.model_copy(update={"target_weight": round(class_target, 4)}))

    cash_target = _clamp(1.0 - allocated_non_cash, 0.0, 1.0)
    finalized: list[AssetClassAllocation] = []
    for allocation in updated_allocations:
        if allocation.class_id == "cash_stable":
            finalized.append(
                allocation.model_copy(
                    update={
                        "target_weight": round(cash_target, 4),
                        "selected_symbols": ["CASH"] if cash_target > 0 else [],
                    }
                )
            )
        else:
            finalized.append(allocation)
    return finalized


def _allocate_within_classes(
    *,
    class_allocations: list[AssetClassAllocation],
    candidates: list[UniverseCandidate],
    signal_map: dict[str, TradingSignal],
    settings,
) -> tuple[dict[str, float], dict[str, int], list[str]]:
    target_by_symbol: dict[str, float] = {}
    selection_order: list[str] = []
    class_candidate_map: dict[str, list[UniverseCandidate]] = {}
    for candidate in candidates:
        class_candidate_map.setdefault(candidate.asset_class, []).append(candidate)

    updated_allocations: list[AssetClassAllocation] = []
    class_selection_lookup: dict[str, list[str]] = {}
    for allocation in class_allocations:
        spec = CLASS_SPEC_BY_ID[allocation.class_id]
        if allocation.class_id == "cash_stable" or allocation.target_weight <= 0 or not spec.live_market_data:
            updated_allocations.append(allocation)
            continue

        ranked_candidates = sorted(
            class_candidate_map.get(allocation.class_id, []),
            key=lambda candidate: _asset_selection_score(signal_map[candidate.symbol], candidate, settings),
            reverse=True,
        )
        selected = ranked_candidates[: spec.max_selected_assets]
        raw_scores = {
            candidate.symbol: _asset_selection_score(signal_map[candidate.symbol], candidate, settings)
            for candidate in selected
            if _asset_selection_score(signal_map[candidate.symbol], candidate, settings) > 0
        }
        if not raw_scores:
            updated_allocations.append(
                allocation.model_copy(
                    update={
                        "selected_symbols": [],
                        "note": f"{allocation.label} retained zero deployed assets because the tactical selector kept the sleeve in cash.",
                    }
                )
            )
            continue

        total_score = sum(raw_scores.values())
        selected_symbols: list[str] = []
        class_deployed_weight = 0.0
        for symbol, raw_score in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True):
            if total_score <= 0:
                symbol_weight = 0.0
            else:
                symbol_weight = allocation.target_weight * (raw_score / total_score)
            symbol_weight = _clamp(symbol_weight, 0.0, settings.max_position_weight)
            if symbol_weight <= 0:
                continue
            target_by_symbol[symbol] = round(symbol_weight, 6)
            selected_symbols.append(symbol)
            class_deployed_weight += symbol_weight
            if symbol not in selection_order:
                selection_order.append(symbol)

        updated_allocations.append(
            allocation.model_copy(
                update={
                    "target_weight": round(class_deployed_weight, 4),
                    "selected_symbols": selected_symbols,
                }
            )
        )
        class_selection_lookup[allocation.class_id] = selected_symbols

    class_allocations[:] = updated_allocations
    rank_lookup = {symbol: index + 1 for index, symbol in enumerate(selection_order)}
    return target_by_symbol, rank_lookup, selection_order


def _asset_selection_score(signal: TradingSignal, candidate: UniverseCandidate, settings) -> float:
    base_ratio = candidate.base_target_weight / max(settings.max_position_weight, 1e-6)
    return _clamp(
        (0.55 * base_ratio)
        + (0.25 * candidate.combined_universe_score)
        + (0.20 * max(signal.regime_score, 0.0)),
        0.0,
        1.0,
    )


def _realized_volatility(bundle: FeatureBundle) -> float:
    returns = np.asarray([row.market_return for row in bundle.rows[-UNIVERSE_RETURN_WINDOW:]], dtype=float)
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1))


def _average_dollar_volume(bundle: FeatureBundle) -> float:
    recent_candles = bundle.candles[-UNIVERSE_VOLUME_WINDOW:]
    if not recent_candles:
        return 0.0
    values = [(candle.close * candle.volume) for candle in recent_candles]
    return float(sum(values) / len(values))


def _beta_to_reference(bundle: FeatureBundle, reference_rows) -> float:
    asset_returns = np.asarray([row.market_return for row in bundle.rows[-UNIVERSE_RETURN_WINDOW:]], dtype=float)
    reference_returns = np.asarray([row.market_return for row in reference_rows[-UNIVERSE_RETURN_WINDOW:]], dtype=float)
    length = min(len(asset_returns), len(reference_returns))
    if length < 2:
        return 1.0 if bundle.pair == REFERENCE_SYMBOL else 0.0
    asset_series = asset_returns[-length:]
    reference_series = reference_returns[-length:]
    reference_variance = float(np.var(reference_series, ddof=1))
    if reference_variance <= 1e-10:
        return 1.0 if bundle.pair == REFERENCE_SYMBOL else 0.0
    covariance = float(np.cov(asset_series, reference_series, ddof=1)[0][1])
    return covariance / reference_variance


def _trend_quality(bundle: FeatureBundle) -> float:
    rows = bundle.rows[-UNIVERSE_VOLUME_WINDOW:]
    if len(rows) < 3:
        return 0.0
    total_return = (rows[-1].close / rows[0].close) - 1.0 if rows[0].close else 0.0
    if abs(total_return) < 1e-6:
        return 0.0
    direction = 1 if total_return > 0 else -1
    aligned = sum(1 for row in rows[1:] if row.market_return * direction > 0)
    direction_consistency = aligned / max(len(rows) - 1, 1)
    strength = min(abs(total_return) / 0.12, 1.0)
    return direction_consistency * strength


def _medium_horizon_trend(bundle: FeatureBundle) -> float:
    rows = bundle.rows[-CLASS_RETURN_WINDOW:]
    if len(rows) < 3 or rows[0].close <= 0:
        return 0.0
    return (rows[-1].close / rows[0].close) - 1.0


def _relative_strength_to_btc(bundle: FeatureBundle, reference_rows) -> float:
    rows = bundle.rows[-CLASS_RETURN_WINDOW:]
    if len(rows) < 3 or rows[0].close <= 0:
        return 0.0
    asset_return = (rows[-1].close / rows[0].close) - 1.0
    if not reference_rows:
        return asset_return
    reference_slice = reference_rows[-len(rows):]
    if len(reference_slice) < 3 or reference_slice[0].close <= 0:
        return asset_return
    reference_return = (reference_slice[-1].close / reference_slice[0].close) - 1.0
    return asset_return - reference_return


def _drawdown(bundle: FeatureBundle) -> float:
    closes = [row.close for row in bundle.rows[-CLASS_DRAWNDOWN_WINDOW:]]
    if len(closes) < 3:
        return 0.0
    peak = max(closes)
    if peak <= 0:
        return 0.0
    return (closes[-1] / peak) - 1.0


def _class_trend(bundles: list[FeatureBundle]) -> float:
    if not bundles:
        return 0.0
    return float(np.mean([_medium_horizon_trend(bundle) for bundle in bundles]))


def _class_relative_strength(bundles: list[FeatureBundle], reference_rows) -> float:
    if not bundles:
        return 0.0
    return float(np.mean([_relative_strength_to_btc(bundle, reference_rows) for bundle in bundles]))


def _class_drawdown(bundles: list[FeatureBundle]) -> float:
    if not bundles:
        return 0.0
    return float(np.mean([_drawdown(bundle) for bundle in bundles]))


def _class_score(*, trend: float, volatility: float, rel_strength: float, drawdown: float) -> float:
    trend_component = _clamp(trend / 0.12, -1.0, 1.0)
    relative_strength_component = _clamp(rel_strength / 0.08, -1.0, 1.0)
    drawdown_component = (2.0 * _clamp(1.0 - abs(drawdown) / 0.25, 0.0, 1.0)) - 1.0
    volatility_component = (2.0 * _volatility_score(volatility)) - 1.0
    return _clamp(
        (0.50 * trend_component)
        + (0.20 * relative_strength_component)
        + (0.15 * drawdown_component)
        + (0.15 * volatility_component),
        -1.0,
        1.0,
    )


def _class_confidence(*, mean_confidence: float, confidence_stability: float, class_score: float) -> float:
    structural_strength = _clamp(abs(class_score), 0.0, 1.0)
    return _clamp(
        (0.45 * mean_confidence)
        + (0.30 * confidence_stability)
        + (0.25 * structural_strength),
        0.0,
        1.0,
    )


def _cash_class_signal(structural_risk_inputs: list[tuple[float, float]]) -> tuple[float, float, str]:
    if not structural_risk_inputs:
        return 1.0, 1.0, "No live risk sleeves are active, so the allocator holds capital in cash."
    downside_pressure = float(np.mean([max(-score, 0.0) for score, _ in structural_risk_inputs]))
    uncertainty = 1.0 - float(np.mean([confidence for _, confidence in structural_risk_inputs]))
    offensive_strength = float(np.max([max(score, 0.0) for score, _ in structural_risk_inputs]))
    cash_score = _clamp((0.60 * downside_pressure) + (0.25 * uncertainty) - (0.25 * offensive_strength), -1.0, 1.0)
    cash_confidence = _clamp((0.60 * downside_pressure) + (0.40 * uncertainty), 0.0, 1.0)
    note = (
        "Cash is an active reserve sleeve. Its weight rises when cross-class downside pressure or uncertainty "
        "dominates the live risk sleeves."
    )
    return cash_score, cash_confidence, note


def _volatility_score(realized_volatility: float) -> float:
    preferred_center = 0.025
    tolerance = 0.03
    return _clamp(1.0 - abs(realized_volatility - preferred_center) / tolerance, 0.0, 1.0)


def _class_category(class_id: str, class_score: float, class_confidence: float) -> str:
    if class_id == "cash_stable":
        return "defensive_reserve"
    if class_score >= 0.35 and class_confidence >= 0.45:
        return "favored"
    if class_score >= 0.05:
        return "watchlist"
    if class_score <= -0.20:
        return "defensive"
    return "neutral"


def _category_label(
    *,
    asset_class: str,
    liquidity_score: float,
    beta_to_btc: float,
    trend_quality: float,
    combined_score: float,
) -> str:
    if asset_class == "crypto_majors":
        return "core_major" if liquidity_score >= 0.75 else "major_watch"
    if liquidity_score >= 0.75 and beta_to_btc >= 1.1 and combined_score >= 0.6:
        return "high_beta_momentum"
    if liquidity_score >= 0.70 and trend_quality >= 0.45:
        return "liquid_trending"
    return "noisy_speculative"


def _candidate_note(class_allocation: AssetClassAllocation, final_target: float) -> str:
    if not class_allocation.live_tradeable:
        return class_allocation.note
    if class_allocation.target_weight <= 0:
        return f"{class_allocation.label} received zero class allocation, so this symbol stays flat."
    if final_target <= 0:
        return f"{class_allocation.label} received capital, but the intra-class selector routed it elsewhere."
    return ""


def _portfolio_policy_reason(
    *,
    signal: TradingSignal,
    candidate: UniverseCandidate,
    class_allocation: AssetClassAllocation,
) -> str:
    if not candidate.live_tradeable:
        return f"{candidate.symbol} is scaffolded in {candidate.asset_class_label} and is not live-tradeable yet."
    if class_allocation.target_weight <= 0:
        return (
            f"{candidate.asset_class_label} scored {class_allocation.class_score:.3f} with confidence "
            f"{class_allocation.class_confidence:.3f}, so the class allocator kept the sleeve in cash."
        )
    if candidate.target_weight <= 0:
        return (
            f"{candidate.asset_class_label} received {class_allocation.target_weight:.4f}, but {candidate.symbol} "
            f"did not win the tactical intra-class allocation despite raw target {signal.base_target_weight:.4f}."
        )
    return (
        f"{candidate.asset_class_label} received {class_allocation.target_weight:.4f} at class level, and "
        f"{candidate.symbol} won the tactical slot with universe score {candidate.combined_universe_score:.3f}, "
        f"mapping raw target {signal.base_target_weight:.4f} to final weight {candidate.target_weight:.4f}."
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
