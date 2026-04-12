from __future__ import annotations

from typing import Protocol


class MarketReader(Protocol):
    def get_snapshot(self, pair: str) -> dict[str, object]:
        ...


class AccountReader(Protocol):
    def status(self) -> dict[str, object]:
        ...


class ExecutionWriter(Protocol):
    def status(self) -> dict[str, object]:
        ...


class StrategyAdapter(Protocol):
    def status(self) -> dict[str, object]:
        ...
