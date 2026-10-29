from typing import Callable, Protocol

from app.domain.models import DataIssue, DataSnapshot, StockData

Progress = Callable[[int, int], None]


class DataProviderError(Exception):
    """Only sanitized internal text. Never attach HTTP requests or upstream messages."""
    def __init__(self, issue: DataIssue):
        self.issue = issue
        super().__init__(issue.message)


class FinancialDataProvider(Protocol):
    """Internal normalized contract only; it makes no claim about external API fields."""
    name: str
    data_mode: str
    universe: str

    def fetch_universe(self, universe: str) -> list[StockData]: ...

    def fetch_snapshot(self, universe: str, progress: Progress | None = None) -> DataSnapshot: ...
