from fastapi import APIRouter

from backend.app.schemas.trading import EngineControlRequest, EngineResetRequest, EngineStatusResponse, TradingRunResponse
from backend.app.services.engine_service import (
    get_engine_status,
    reset_engine_state,
    run_engine_once,
    start_engine,
    stop_engine,
)


router = APIRouter()


@router.get("/engine/status", response_model=EngineStatusResponse)
def engine_status() -> EngineStatusResponse:
    return get_engine_status()


@router.post("/engine/run-once", response_model=TradingRunResponse)
def engine_run_once(request: EngineControlRequest | None = None) -> TradingRunResponse:
    payload = request or EngineControlRequest()
    return run_engine_once(pair=payload.pair, trigger="manual")


@router.post("/engine/start", response_model=EngineStatusResponse)
def engine_start(request: EngineControlRequest) -> EngineStatusResponse:
    return start_engine(request)


@router.post("/engine/stop", response_model=EngineStatusResponse)
def engine_stop() -> EngineStatusResponse:
    return stop_engine()


@router.post("/engine/reset", response_model=EngineStatusResponse)
def engine_reset(request: EngineResetRequest) -> EngineStatusResponse:
    return reset_engine_state(request)
