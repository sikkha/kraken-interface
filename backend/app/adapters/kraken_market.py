from __future__ import annotations

import shutil
import time
from math import sin

from client import run_command
from client import get_ticker
from parser import parse_ticker


class KrakenMarketReadError(Exception):
    """Raised when a live Kraken market read cannot be completed."""


class KrakenMarketAdapter:
    """Live-compatible market adapter with a mock mode for scaffold work."""

    def __init__(self, source_mode: str = "mock") -> None:
        self.source_mode = source_mode

    def get_snapshot(self, pair: str) -> dict[str, object]:
        if self.source_mode == "live":
            try:
                raw = get_ticker(pair)
                parsed = parse_ticker(raw)
                return {
                    "pair": parsed["pair"],
                    "bid": parsed["bid"],
                    "ask": parsed["ask"],
                    "last": parsed["last"],
                    "mid": parsed["mid"],
                    "spread": parsed["spread"],
                    "timestamp_ms": parsed["timestamp"],
                    "source": "live",
                    "live_compatible": True,
                }
            except Exception as exc:
                raise KrakenMarketReadError(str(exc)) from exc

        return self._mock_snapshot(pair)

    def fallback_snapshot(self, pair: str) -> dict[str, object]:
        return self._mock_snapshot(pair)

    def get_candles(self, pair: str, interval: int = 1, limit: int = 120) -> dict[str, object]:
        if self.source_mode == "live":
            try:
                raw = run_command(["kraken", "ohlc", pair, "--interval", str(interval), "-o", "json"], timeout=10)
                return self._normalize_live_candles(raw=raw, pair=pair, interval=interval, limit=limit)
            except Exception as exc:
                raise KrakenMarketReadError(str(exc)) from exc

        return self.fallback_candles(pair=pair, interval=interval, limit=limit)

    def fallback_candles(self, pair: str, interval: int = 1, limit: int = 120) -> dict[str, object]:
        return self._mock_candles(pair=pair, interval=interval, limit=limit)

    def status(self) -> dict[str, object]:
        if self.source_mode == "mock":
            return {
                "name": "kraken_market_adapter",
                "role": "market_reader",
                "ready": True,
                "mode": "mock",
                "notes": "Serving scaffold-safe mock snapshots. Live Kraken reads remain available behind the same contract.",
            }

        binary_path = shutil.which("kraken")
        if binary_path:
            return {
                "name": "kraken_market_adapter",
                "role": "market_reader",
                "ready": True,
                "mode": "live",
                "notes": (
                    f"Kraken CLI detected at {binary_path}. Live market snapshots are attempted first "
                    "and fall back to mock data if a read fails."
                ),
            }

        return {
            "name": "kraken_market_adapter",
            "role": "market_reader",
            "ready": False,
            "mode": "live",
            "notes": "KRAKEN_MARKET_SOURCE=live is set, but the Kraken CLI binary is not available in this runtime.",
        }

    def _mock_snapshot(self, pair: str) -> dict[str, object]:
        last = 67420.5
        spread = 14.25
        bid = last - (spread / 2)
        ask = last + (spread / 2)
        return {
            "pair": pair.upper(),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "last": last,
            "mid": round((bid + ask) / 2, 2),
            "spread": round(spread, 2),
            "timestamp_ms": int(time.time() * 1000),
            "source": "mock",
            "live_compatible": True,
        }

    def _normalize_live_candles(
        self,
        raw: dict[str, object],
        pair: str,
        interval: int,
        limit: int,
    ) -> dict[str, object]:
        normalized_pair = pair.upper()
        raw_pair = next((key for key in raw.keys() if key != "last"), None)
        if not raw_pair:
            raise KrakenMarketReadError("Kraken OHLC response did not contain candle rows.")

        rows = raw.get(raw_pair)
        if not isinstance(rows, list) or not rows:
            raise KrakenMarketReadError("Kraken OHLC response returned no candle data.")

        candles = []
        for row in rows[-limit:]:
            if not isinstance(row, list) or len(row) < 7:
                continue
            candles.append(
                {
                    "timestamp_ms": int(float(row[0]) * 1000),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[6]),
                }
            )

        if not candles:
            raise KrakenMarketReadError("Kraken OHLC response could not be normalized into candles.")

        return {
            "pair": normalized_pair,
            "interval": interval,
            "source": "live",
            "live_compatible": True,
            "candles": candles,
        }

    def _mock_candles(self, pair: str, interval: int, limit: int) -> dict[str, object]:
        now_ms = int(time.time() * 1000)
        step_ms = max(interval, 1) * 60 * 1000
        base_price = 67420.5
        candles = []

        for index in range(limit):
            ts = now_ms - ((limit - index) * step_ms)
            drift = sin(index / 6) * 95
            open_price = base_price + drift
            close_price = open_price + sin(index / 3) * 22
            high_price = max(open_price, close_price) + 18 + abs(sin(index / 4) * 10)
            low_price = min(open_price, close_price) - 18 - abs(sin(index / 5) * 10)
            volume = 0.8 + abs(sin(index / 7) * 3.2)
            candles.append(
                {
                    "timestamp_ms": ts,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": round(volume, 6),
                }
            )

        return {
            "pair": pair.upper(),
            "interval": interval,
            "source": "mock",
            "live_compatible": True,
            "candles": candles,
        }
