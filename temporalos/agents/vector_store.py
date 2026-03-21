"""TF-IDF in-memory vector store for the Q&A agent.

Zero external dependencies — works with Python stdlib only.
Swap out for Chroma/Qdrant/Pinecone by replacing TFIDFStore with
any store that exposes add(doc) and search(query, top_k) → list[Document].
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Document:
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TFIDFStore:
    """Minimal TF-IDF relevance store.

    fit_transform is done lazily on first query so bulk inserts are O(n).
    Thread-safety: not guaranteed (single-process use expected).
    """

    def __init__(self) -> None:
        self._docs: Dict[str, Document] = {}
        self._tf: Dict[str, Counter] = {}   # doc_id → term counts
        self._idf: Dict[str, float] = {}    # term → idf score
        self._dirty = True

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\b[a-z]{2,}\b", text.lower())

    def add(self, doc: Document) -> None:
        self._docs[doc.id] = doc
        self._tf[doc.id] = Counter(self._tokenize(doc.text))
        self._dirty = True

    def remove(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)
        self._tf.pop(doc_id, None)
        self._dirty = True

    def _build_idf(self) -> None:
        if not self._dirty:
            return
        n = len(self._docs)
        if n == 0:
            self._idf = {}
            self._dirty = False
            return
        df: Counter = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        self._idf = {
            term: math.log(1.0 + n / count)
            for term, count in df.items()
        }
        self._dirty = False

    def _score(self, doc_id: str, query_tokens: List[str]) -> float:
        tf = self._tf.get(doc_id, Counter())
        # Normalise TF by document length
        total = sum(tf.values()) or 1
        return sum(
            (tf.get(t, 0) / total) * self._idf.get(t, 0)
            for t in query_tokens
        )

    def search(self, query: str, top_k: int = 5,
               filter_meta: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
        self._build_idf()
        if not self._docs:
            return []
        tokens = self._tokenize(query)
        candidates = {
            doc_id: doc
            for doc_id, doc in self._docs.items()
            if not filter_meta or all(
                doc.metadata.get(k) == v for k, v in filter_meta.items()
            )
        }
        scored = [
            (doc, self._score(doc_id, tokens))
            for doc_id, doc in candidates.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(doc, sc) for doc, sc in scored[:top_k] if sc > 0]

    def __len__(self) -> int:
        return len(self._docs)

    def clear(self) -> None:
        self._docs.clear()
        self._tf.clear()
        self._idf.clear()
        self._dirty = True
