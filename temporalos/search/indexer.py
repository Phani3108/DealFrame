"""In-memory TF-IDF search index for video segments.

No external dependencies — pure Python implementation using an inverted index
with TF-IDF scoring. Thread-safe for concurrent reads/writes.

In a production deployment this would back onto pgvector or Elasticsearch,
but the interface is identical so swapping backends requires no caller changes.
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field


@dataclass
class IndexEntry:
    """A single indexed extraction record."""

    doc_id: str  # "{video_id}:{timestamp_ms}"
    video_id: str
    timestamp_ms: int
    timestamp_str: str
    topic: str
    risk: str
    risk_score: float
    objections: list[str]
    decision_signals: list[str]
    transcript: str
    model: str

    @property
    def searchable_text(self) -> str:
        return " ".join(
            filter(
                None,
                [
                    self.topic,
                    self.transcript,
                    " ".join(self.objections),
                    " ".join(self.decision_signals),
                ],
            )
        ).lower()


@dataclass
class SearchResult:
    entry: IndexEntry
    score: float

    def to_dict(self) -> dict:
        return {
            "doc_id": self.entry.doc_id,
            "video_id": self.entry.video_id,
            "timestamp_ms": self.entry.timestamp_ms,
            "timestamp_str": self.entry.timestamp_str,
            "topic": self.entry.topic,
            "risk": self.entry.risk,
            "risk_score": self.entry.risk_score,
            "transcript_snippet": self.entry.transcript[:200],
            "objections": self.entry.objections,
            "decision_signals": self.entry.decision_signals,
            "score": round(self.score, 4),
        }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z]{2,}\b", text.lower())


class SearchIndex:
    """
    Thread-safe in-memory inverted index with TF-IDF scoring.

    Entries are added via `index()` and queried via `search()`.
    `clear()` resets the index without restarting the process.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._docs: dict[str, IndexEntry] = {}
        self._inverted: dict[str, set[str]] = {}  # term → {doc_id}
        self._df: dict[str, int] = {}  # document frequency per term

    def index(self, entry: IndexEntry) -> None:
        with self._lock:
            doc_id = entry.doc_id
            if doc_id in self._docs:
                self._remove_doc_locked(doc_id)
            self._docs[doc_id] = entry
            tokens = set(_tokenize(entry.searchable_text))
            for term in tokens:
                self._inverted.setdefault(term, set()).add(doc_id)
                self._df[term] = self._df.get(term, 0) + 1

    def search(
        self,
        query: str,
        risk_filter: str | None = None,
        topic_filter: str | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        with self._lock:
            n_docs = len(self._docs)
            if n_docs == 0:
                return []

            candidate_scores: dict[str, float] = {}
            for term in query_tokens:
                matching = self._inverted.get(term, set())
                if not matching:
                    continue
                idf = math.log((n_docs + 1) / (len(matching) + 1)) + 1.0
                for doc_id in matching:
                    entry = self._docs[doc_id]
                    tokens_in_doc = _tokenize(entry.searchable_text)
                    tf = tokens_in_doc.count(term) / max(len(tokens_in_doc), 1)
                    candidate_scores[doc_id] = candidate_scores.get(doc_id, 0) + tf * idf

            results: list[SearchResult] = []
            for doc_id, score in candidate_scores.items():
                entry = self._docs[doc_id]
                if risk_filter and entry.risk != risk_filter:
                    continue
                if topic_filter and entry.topic != topic_filter:
                    continue
                results.append(SearchResult(entry=entry, score=score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _remove_doc_locked(self, doc_id: str) -> None:
        """Remove a doc's tokens from the index. Caller must hold self._lock."""
        entry = self._docs.pop(doc_id, None)
        if entry is None:
            return
        tokens = set(_tokenize(entry.searchable_text))
        for term in tokens:
            self._inverted.get(term, set()).discard(doc_id)
            if not self._inverted.get(term):
                self._inverted.pop(term, None)
                self._df.pop(term, None)
            else:
                self._df[term] = max(0, self._df.get(term, 1) - 1)

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()
            self._inverted.clear()
            self._df.clear()

    @property
    def document_count(self) -> int:
        return len(self._docs)


_global_index: SearchIndex | None = None
_index_lock = threading.Lock()


def get_search_index() -> SearchIndex:
    global _global_index
    with _index_lock:
        if _global_index is None:
            _global_index = SearchIndex()
    return _global_index
