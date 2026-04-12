from __future__ import annotations

from backend.app.adapters.kraken_market import KrakenMarketAdapter, KrakenMarketReadError
from backend.app.core.config import get_settings
from backend.app.schemas.market import MarketCandlesResponse, MarketSnapshot
from backend.app.services.event_log import emit_event


def get_market_snapshot(pair: str) -> MarketSnapshot:
    settings = get_settings()
    adapter = KrakenMarketAdapter(source_mode=settings.kraken_market_source)
    requested_pair = pair or settings.default_pair

    try:
        snapshot = adapter.get_snapshot(pair=requested_pair)
    except KrakenMarketReadError as exc:
        snapshot = adapter.fallback_snapshot(pair=requested_pair)
        emit_event(
            level="ERROR",
            component="market",
            message="Live market read failed. Serving mock fallback snapshot.",
            data={
                "pair": requested_pair,
                "requested_source": settings.kraken_market_source,
                "fallback_source": str(snapshot["source"]),
                "error": str(exc),
            },
        )
    else:
        emit_event(
            level="INFO",
            component="market",
            message="Market snapshot served.",
            data={"pair": str(snapshot["pair"]), "source": str(snapshot["source"])},
        )
    return MarketSnapshot.model_validate(snapshot)


def get_market_candles(pair: str, interval: int = 1, limit: int = 120) -> MarketCandlesResponse:
    settings = get_settings()
    adapter = KrakenMarketAdapter(source_mode=settings.kraken_market_source)
    requested_pair = pair or settings.default_pair

    try:
        candles = adapter.get_candles(pair=requested_pair, interval=interval, limit=limit)
    except KrakenMarketReadError as exc:
        candles = adapter.fallback_candles(pair=requested_pair, interval=interval, limit=limit)
        emit_event(
            level="ERROR",
            component="market",
            message="Live candle read failed. Serving mock fallback candles.",
            data={
                "pair": requested_pair,
                "interval": interval,
                "requested_source": settings.kraken_market_source,
                "fallback_source": str(candles["source"]),
                "error": str(exc),
            },
        )
    else:
        emit_event(
            level="INFO",
            component="market",
            message="Market candles served.",
            data={
                "pair": str(candles["pair"]),
                "interval": interval,
                "source": str(candles["source"]),
                "count": len(candles["candles"]),
            },
        )

    return MarketCandlesResponse.model_validate(candles)
