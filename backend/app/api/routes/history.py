from fastapi import APIRouter, Query

from backend.app.schemas.history import (
    HistoryCyclesResponse,
    HistoryExecutionsResponse,
    HistoryPortfolioResponse,
    HistoryRiskResponse,
    HistorySignalsResponse,
)
from backend.app.services.history_ledger import SqliteHistoryLedger


router = APIRouter()


@router.get("/history/cycles", response_model=HistoryCyclesResponse)
def history_cycles(limit: int = Query(default=50, ge=1, le=500)) -> HistoryCyclesResponse:
    ledger = SqliteHistoryLedger()
    return HistoryCyclesResponse(db_path=ledger.database_path(), cycles=ledger.list_cycles(limit=limit))


@router.get("/history/signals", response_model=HistorySignalsResponse)
def history_signals(limit: int = Query(default=50, ge=1, le=500)) -> HistorySignalsResponse:
    ledger = SqliteHistoryLedger()
    return HistorySignalsResponse(db_path=ledger.database_path(), signals=ledger.list_signals(limit=limit))


@router.get("/history/risk-decisions", response_model=HistoryRiskResponse)
def history_risk_decisions(limit: int = Query(default=50, ge=1, le=500)) -> HistoryRiskResponse:
    ledger = SqliteHistoryLedger()
    return HistoryRiskResponse(db_path=ledger.database_path(), decisions=ledger.list_risk_decisions(limit=limit))


@router.get("/history/executions", response_model=HistoryExecutionsResponse)
def history_executions(limit: int = Query(default=50, ge=1, le=500)) -> HistoryExecutionsResponse:
    ledger = SqliteHistoryLedger()
    return HistoryExecutionsResponse(db_path=ledger.database_path(), executions=ledger.list_executions(limit=limit))


@router.get("/history/portfolio", response_model=HistoryPortfolioResponse)
def history_portfolio(limit: int = Query(default=200, ge=1, le=1000)) -> HistoryPortfolioResponse:
    ledger = SqliteHistoryLedger()
    return HistoryPortfolioResponse(db_path=ledger.database_path(), snapshots=ledger.list_portfolio_snapshots(limit=limit))

