from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.trading import TradingRunResponse, TradingStatusResponse
from backend.app.services.engine_service import run_engine_once
from backend.app.services.trading_loop_service import get_trading_status


router = APIRouter()


@router.get("/trading/status", response_model=TradingStatusResponse)
def trading_status(pair: str = Query(default="BTCUSD")) -> TradingStatusResponse:
    try:
        return get_trading_status(pair=pair)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/trading/run-once", response_model=TradingRunResponse)
def trading_run_once(pair: str = Query(default="BTCUSD")) -> TradingRunResponse:
    try:
        return run_engine_once(pair=pair, trigger="manual")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
