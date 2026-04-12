from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    pair: str = Field(..., examples=["BTCUSD"])
    bid: float
    ask: float
    last: float
    mid: float
    spread: float
    timestamp_ms: int
    source: str = Field(..., examples=["mock", "live"])
    live_compatible: bool = True


class MarketCandle(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketCandlesResponse(BaseModel):
    pair: str = Field(..., examples=["BTCUSD"])
    interval: int = Field(..., examples=[1, 5, 15])
    source: str = Field(..., examples=["mock", "live"])
    live_compatible: bool = True
    candles: list[MarketCandle]
