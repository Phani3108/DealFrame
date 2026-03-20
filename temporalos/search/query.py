"""Search query builder and engine — thin wrapper over SearchIndex."""

from __future__ import annotations

from dataclasses import dataclass

from .indexer import IndexEntry, SearchIndex, SearchResult, get_search_index


@dataclass
class SearchQuery:
    text: str = ""
    risk: str | None = None   # low | medium | high
    topic: str | None = None
    limit: int = 20

    def is_valid(self) -> bool:
        return bool(self.text.strip())


class SearchEngine:
    def __init__(self, index: SearchIndex | None = None) -> None:
        self._index = index or get_search_index()

    def search(self, query: SearchQuery) -> list[SearchResult]:
        if not query.is_valid():
            return []
        return self._index.search(
            query=query.text,
            risk_filter=query.risk,
            topic_filter=query.topic,
            limit=query.limit,
        )

    def index_extraction(
        self,
        video_id: str,
        timestamp_ms: int,
        timestamp_str: str,
        topic: str,
        risk: str,
        risk_score: float,
        objections: list[str],
        decision_signals: list[str],
        transcript: str,
        model: str,
    ) -> None:
        entry = IndexEntry(
            doc_id=f"{video_id}:{timestamp_ms}",
            video_id=video_id,
            timestamp_ms=timestamp_ms,
            timestamp_str=timestamp_str,
            topic=topic,
            risk=risk,
            risk_score=risk_score,
            objections=objections,
            decision_signals=decision_signals,
            transcript=transcript,
            model=model,
        )
        self._index.index(entry)
