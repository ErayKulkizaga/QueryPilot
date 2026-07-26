from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.analysis.rule_engine import RuleAnalysis


class AnalysisNotFoundError(KeyError):
    """Raised when an analysis ID is absent or expired."""


@dataclass(frozen=True, slots=True)
class StoredAnalysis:
    analysis: RuleAnalysis
    created_at: float


class InMemoryAnalysisStore:
    def __init__(
        self,
        *,
        ttl_seconds: int = 900,
        max_items: int = 256,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_items = max_items
        self._items: dict[str, StoredAnalysis] = {}
        self._lock = Lock()

    def _prune(self, now: float) -> None:
        expired = [
            analysis_id
            for analysis_id, item in self._items.items()
            if now - item.created_at > self._ttl_seconds
        ]
        for analysis_id in expired:
            self._items.pop(analysis_id, None)
        while len(self._items) >= self._max_items:
            oldest_id = min(
                self._items,
                key=lambda analysis_id: self._items[analysis_id].created_at,
            )
            self._items.pop(oldest_id)

    def put(self, analysis: RuleAnalysis) -> str:
        now = monotonic()
        analysis_id = uuid4().hex
        with self._lock:
            self._prune(now)
            self._items[analysis_id] = StoredAnalysis(
                analysis=analysis,
                created_at=now,
            )
        return analysis_id

    def get(self, analysis_id: str) -> RuleAnalysis:
        now = monotonic()
        with self._lock:
            item = self._items.get(analysis_id)
            if item is None or now - item.created_at > self._ttl_seconds:
                self._items.pop(analysis_id, None)
                raise AnalysisNotFoundError(analysis_id)
            return item.analysis


@lru_cache(maxsize=4)
def get_analysis_store(ttl_seconds: int = 900) -> InMemoryAnalysisStore:
    return InMemoryAnalysisStore(ttl_seconds=ttl_seconds)
