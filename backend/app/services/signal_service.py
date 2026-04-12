from __future__ import annotations

import time

import numpy as np

from backend.app.core.config import get_settings
from backend.app.schemas.trading import FeatureSummary, TradingSignal
from backend.app.services.feature_service import FeatureBundle, feature_matrix_from_rows, has_sufficient_history
from backend.app.signal_engine import load_signal_artifact, run_gru_series


FALLBACK_MODEL_VERSION = "notebook-proxy-online-v2"


def generate_signal(bundle: FeatureBundle) -> TradingSignal:
    settings = get_settings()
    timestamp_ms = int(time.time() * 1000)
    artifact_status, artifact = load_signal_artifact()

    if not has_sufficient_history(bundle):
        summary = _empty_summary(bundle, confidence_method="insufficient_history")
        return TradingSignal(
            symbol=bundle.pair,
            signal="hold",
            confidence=0.0,
            base_target_weight=0.0,
            target_weight=0.0,
            regime_score=0.0,
            exposure_state="flat",
            action_policy_reason="Insufficient candle history to map regime score into an exposure target.",
            model_version=artifact_status.model_version,
            timestamp_ms=timestamp_ms,
            engine_type=artifact_status.engine_type,
            artifact_status=artifact_status.status,
            artifact_loaded=artifact_status.loaded,
            artifact_path=artifact_status.path,
            runtime_note=artifact_status.reason,
            features_summary=summary,
            inference_mode=artifact_status.engine_type,
        )

    rows = bundle.rows
    feature_matrix = np.asarray(feature_matrix_from_rows(rows), dtype=float)
    runtime_note = artifact_status.reason
    if artifact is not None:
        try:
            predicted_macd_series = run_gru_series(feature_matrix=feature_matrix, artifact=artifact)
            engine_type = "gru_packaged"
            model_version = artifact.status.model_version
            artifact_loaded = True
        except Exception as exc:
            predicted_macd_series = np.asarray([row.macd for row in rows], dtype=float)
            engine_type = "notebook_proxy"
            model_version = FALLBACK_MODEL_VERSION
            artifact_status = artifact_status.__class__(
                engine_type="notebook_proxy",
                status="runtime_failed_fallback",
                loaded=False,
                path=artifact_status.path,
                model_version=FALLBACK_MODEL_VERSION,
                hidden_size=artifact_status.hidden_size,
                sequence_length=artifact_status.sequence_length,
                reason=f"Packaged inference failed and fell back to notebook_proxy: {exc}",
            )
            artifact_loaded = False
            runtime_note = artifact_status.reason
    else:
        predicted_macd_series = np.asarray([row.macd for row in rows], dtype=float)
        engine_type = "notebook_proxy"
        model_version = FALLBACK_MODEL_VERSION
        artifact_loaded = False

    latest = rows[-1]
    previous_predicted = float(predicted_macd_series[-2]) if len(predicted_macd_series) > 1 else 0.0
    predicted_macd = float(predicted_macd_series[-1])
    predicted_delta = predicted_macd - previous_predicted
    regime_score, score_scale = _compute_regime_score(rows, predicted_macd, predicted_delta)
    persistence_ratio = _persistence_ratio(predicted_macd_series, settings.signal_feature_window)
    confidence_raw = abs(regime_score) * (0.55 + (0.45 * persistence_ratio)) * _volatility_multiplier(rows)
    confidence = _calibrate_confidence(confidence_raw)
    normalized_score = _normalized_score(regime_score)
    target_weight = _target_weight_for_score(normalized_score, confidence)
    exposure_state = _exposure_state(target_weight)
    policy_band = _policy_band(target_weight)

    if target_weight <= settings.rebalance_deadband_weight / 2:
        signal = "sell"
    elif regime_score >= settings.signal_buy_score_threshold:
        signal = "buy"
    else:
        signal = "hold"

    summary = FeatureSummary(
        latest_close=latest.close,
        latest_return=latest.market_return,
        ema12=latest.ema12,
        ema26=latest.ema26,
        rolling_volatility=latest.rolling_volatility,
        macd=latest.macd,
        signal_line=latest.signal_line,
        macd_diff=latest.macd_diff,
        lagged_macd=latest.lagged_macd,
        lagged_signal=latest.lagged_signal,
        predicted_macd=round(predicted_macd, 6),
        previous_predicted_macd=round(previous_predicted, 6),
        predicted_delta=round(predicted_delta, 6),
        confidence_raw=round(confidence_raw, 6),
        confidence_method="tanh_calibrated_regime_strength_with_persistence_and_volatility_penalty",
        regime_score=round(regime_score, 6),
        normalized_score=round(normalized_score, 6),
        score_scale=round(score_scale, 6),
        persistence_ratio=round(persistence_ratio, 4),
        policy_band=policy_band,
        candles_used=len(bundle.candles),
        feature_window=settings.signal_feature_window,
        candle_interval_minutes=bundle.interval,
        candle_source=bundle.source,
    )

    return TradingSignal(
        symbol=bundle.pair,
        signal=signal,
        confidence=round(confidence, 4),
        base_target_weight=round(target_weight, 4),
        target_weight=round(target_weight, 4),
        regime_score=round(regime_score, 4),
        exposure_state=exposure_state,
        action_policy_reason=_policy_reason(
            engine_type=engine_type,
            regime_score=regime_score,
            normalized_score=normalized_score,
            target_weight=target_weight,
            exposure_state=exposure_state,
            policy_band=policy_band,
        ),
        model_version=model_version,
        timestamp_ms=timestamp_ms,
        engine_type=engine_type,
        artifact_status=artifact_status.status,
        artifact_loaded=artifact_loaded,
        artifact_path=artifact_status.path,
        runtime_note=runtime_note,
        features_summary=summary,
        inference_mode=engine_type,
    )


def _compute_regime_score(rows, predicted_macd: float, predicted_delta: float) -> tuple[float, float]:
    settings = get_settings()
    recent_rows = rows[-settings.signal_feature_window :]
    macd_abs = np.asarray([abs(row.macd) for row in recent_rows], dtype=float)
    diff_abs = np.asarray([abs(row.macd_diff) for row in recent_rows], dtype=float)
    macd_scale = float(np.mean(macd_abs)) if len(macd_abs) else 0.0
    diff_scale = float(np.mean(diff_abs)) if len(diff_abs) else 0.0
    score_scale = max(macd_scale, diff_scale * 2.5, abs(rows[-1].macd), 1e-4)
    delta_scale = max(diff_scale, abs(predicted_delta), 1e-4)

    macd_component = float(np.tanh(predicted_macd / score_scale))
    delta_component = float(np.tanh(predicted_delta / delta_scale))
    diff_component = float(np.tanh(rows[-1].macd_diff / delta_scale))
    regime_score = (0.65 * macd_component) + (0.2 * diff_component) + (0.15 * delta_component)
    return _clamp(regime_score, -1.0, 1.0), score_scale


def _persistence_ratio(predicted_macd_series: np.ndarray, feature_window: int) -> float:
    recent_predictions = predicted_macd_series[-feature_window:]
    if len(recent_predictions) == 0:
        return 0.0
    current_positive = (recent_predictions > 0).astype(float)
    previous_positive = np.roll(current_positive, 1)
    previous_positive[0] = 0.0
    persistence = (current_positive + previous_positive) / 2.0
    return float(np.mean(persistence))


def _volatility_multiplier(rows) -> float:
    settings = get_settings()
    recent_rows = rows[-settings.signal_feature_window :]
    recent_volatility = np.asarray([row.rolling_volatility for row in recent_rows], dtype=float)
    valid_volatility = recent_volatility[recent_volatility > 0]
    if not len(valid_volatility):
        return 1.0

    baseline = float(np.mean(valid_volatility))
    latest_volatility = float(valid_volatility[-1])
    if baseline <= 0 or latest_volatility <= 0:
        return 1.0

    ratio = latest_volatility / baseline
    return _clamp(1.15 - (0.2 * max(ratio - 1.0, 0.0)), 0.55, 1.1)


def _calibrate_confidence(confidence_raw: float) -> float:
    return _clamp(float(np.tanh(confidence_raw * 1.4)), 0.0, 1.0)


def _normalized_score(regime_score: float) -> float:
    settings = get_settings()
    normalized_score = (regime_score - settings.signal_flat_score_threshold) / max(
        settings.signal_full_score_threshold - settings.signal_flat_score_threshold,
        1e-4,
    )
    return _clamp(normalized_score, 0.0, 1.0)


def _target_weight_for_score(normalized_score: float, confidence: float) -> float:
    settings = get_settings()
    if normalized_score <= 0:
        return 0.0

    dynamic_multiplier = 0.65 + (0.35 * confidence)
    target_weight = settings.max_position_weight * normalized_score * dynamic_multiplier
    return _clamp(target_weight, 0.0, settings.max_position_weight)


def _exposure_state(target_weight: float) -> str:
    settings = get_settings()
    if target_weight <= 0.0:
        return "flat"
    ratio = target_weight / max(settings.max_position_weight, 1e-6)
    if ratio < 0.34:
        return "light_long"
    if ratio < 0.74:
        return "medium_long"
    return "full_long"


def _policy_band(target_weight: float) -> str:
    if target_weight <= 0:
        return "flat"
    if target_weight <= 0.06:
        return "exploratory_long"
    if target_weight <= 0.14:
        return "core_long"
    return "conviction_long"


def _policy_reason(
    *,
    engine_type: str,
    regime_score: float,
    normalized_score: float,
    target_weight: float,
    exposure_state: str,
    policy_band: str,
) -> str:
    settings = get_settings()
    if target_weight <= 0:
        return (
            f"Regime score {regime_score:.3f} stayed below the flat threshold "
            f"{settings.signal_flat_score_threshold:.2f}, so the policy targets flat exposure."
        )
    return (
        f"{engine_type} produced regime score {regime_score:.3f}, which normalized to {normalized_score:.3f} "
        f"and maps to {policy_band} / {exposure_state} with target weight {target_weight:.4f} "
        f"under the continuous long/flat portfolio policy."
    )


def _empty_summary(bundle: FeatureBundle, confidence_method: str) -> FeatureSummary:
    settings = get_settings()
    latest_close = bundle.candles[-1].close if bundle.candles else 0.0
    return FeatureSummary(
        latest_close=latest_close,
        latest_return=0.0,
        ema12=latest_close,
        ema26=latest_close,
        rolling_volatility=0.0,
        macd=0.0,
        signal_line=0.0,
        macd_diff=0.0,
        lagged_macd=0.0,
        lagged_signal=0.0,
        predicted_macd=0.0,
        previous_predicted_macd=0.0,
        predicted_delta=0.0,
        confidence_raw=0.0,
        confidence_method=confidence_method,
        regime_score=0.0,
        normalized_score=0.0,
        score_scale=0.0,
        persistence_ratio=0.0,
        policy_band="flat",
        candles_used=len(bundle.candles),
        feature_window=settings.signal_feature_window,
        candle_interval_minutes=bundle.interval,
        candle_source=bundle.source,
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
