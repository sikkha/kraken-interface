from __future__ import annotations

import math
from dataclasses import dataclass

from backend.app.schemas.market import MarketCandle, MarketCandlesResponse


VOLATILITY_LOOKBACK = 20
MIN_FEATURE_HISTORY = 50


@dataclass(frozen=True)
class FeatureRow:
    timestamp_ms: int
    price: float
    ema12: float
    ema26: float
    close: float
    market_return: float
    macd: float
    signal_line: float
    macd_diff: float
    lagged_macd: float
    lagged_signal: float
    rolling_volatility: float


@dataclass(frozen=True)
class FeatureBundle:
    pair: str
    interval: int
    source: str
    candles: list[MarketCandle]
    rows: list[FeatureRow]


def build_feature_bundle(candles_response: MarketCandlesResponse) -> FeatureBundle:
    candles = sorted(candles_response.candles, key=lambda candle: candle.timestamp_ms)
    closes = [candle.close for candle in candles]
    if len(closes) < 2:
        return FeatureBundle(
            pair=candles_response.pair,
            interval=candles_response.interval,
            source=candles_response.source,
            candles=candles,
            rows=[],
        )

    alpha_12 = 2 / (12 + 1)
    alpha_26 = 2 / (26 + 1)
    alpha_signal = 2 / (9 + 1)

    ema12 = closes[0]
    ema26 = closes[0]
    signal_line = 0.0
    lagged_macd = 0.0
    lagged_signal = 0.0
    returns_window: list[float] = []
    rows: list[FeatureRow] = []
    previous_close = closes[0]

    for candle in candles:
        close = candle.close
        market_return = 0.0 if previous_close == 0 else (close / previous_close) - 1.0
        previous_close = close

        ema12 = (close * alpha_12) + (ema12 * (1 - alpha_12))
        ema26 = (close * alpha_26) + (ema26 * (1 - alpha_26))
        macd = ema12 - ema26
        signal_line = (macd * alpha_signal) + (signal_line * (1 - alpha_signal))
        macd_diff = macd - signal_line

        returns_window.append(market_return)
        if len(returns_window) > VOLATILITY_LOOKBACK:
            returns_window.pop(0)

        rolling_volatility = _sample_standard_deviation(returns_window)
        rows.append(
            FeatureRow(
                timestamp_ms=candle.timestamp_ms,
                price=close,
                ema12=ema12,
                ema26=ema26,
                close=close,
                market_return=market_return,
                macd=macd,
                signal_line=signal_line,
                macd_diff=macd_diff,
                lagged_macd=lagged_macd,
                lagged_signal=lagged_signal,
                rolling_volatility=rolling_volatility,
            )
        )

        lagged_macd = macd
        lagged_signal = signal_line

    return FeatureBundle(
        pair=candles_response.pair,
        interval=candles_response.interval,
        source=candles_response.source,
        candles=candles,
        rows=rows[1:],
    )


def has_sufficient_history(bundle: FeatureBundle) -> bool:
    return len(bundle.rows) >= MIN_FEATURE_HISTORY


def feature_matrix_from_rows(rows: list[FeatureRow]) -> list[list[float]]:
    return [
        [row.lagged_macd, row.lagged_signal, row.macd_diff]
        for row in rows
    ]


def _sample_standard_deviation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))
