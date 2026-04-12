from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.market import MarketCandlesResponse, MarketSnapshot
from backend.app.services.market_service import get_market_candles, get_market_snapshot


router = APIRouter()


@router.get("/market/snapshot", response_model=MarketSnapshot)
def market_snapshot(pair: str = Query(default="BTCUSD")) -> MarketSnapshot:
    try:
        return get_market_snapshot(pair=pair)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/candles", response_model=MarketCandlesResponse)
def market_candles(
    pair: str = Query(default="BTCUSD"),
    interval: int = Query(default=1, ge=1, le=1440),
    limit: int = Query(default=120, ge=20, le=720),
) -> MarketCandlesResponse:
    try:
        return get_market_candles(pair=pair, interval=interval, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
