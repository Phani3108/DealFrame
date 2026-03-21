"""Semantic vector store — real embeddings with SQLite persistence.

Supports two backends:
  1. Local: sentence-transformers (all-MiniLM-L6-v2) + numpy cosine similarity
  2. OpenAI: text-embedding-3-small via API

Falls back to TF-IDF if neither is available (zero-dependency mode).
Persistence: stores embeddings as JSON blobs in SQLite.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Document:
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class SemanticStore:
    """Embedding-backed vector store with SQLite persistence."""

    def __init__(self, db_path: str = "", embed_model: str = "auto"):
        self._docs: Dict[str, Document] = {}
        self._db_path = db_path
        self._embed_fn = self._resolve_embedder(embed_model)
        self._dim = 0
        if db_path:
            self._load_from_db()

    def _resolve_embedder(self, model: str):
        """Pick the best available embedding function."""
        if model == "openai":
            return self._embed_openai
        if model == "local":
            return self._try_local_embed() or self._embed_tfidf
        # auto: try local first, then openai, then tfidf
        local = self._try_local_embed()
        if local:
            return local
        return self._embed_tfidf

    def _try_local_embed(self):
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            self._dim = 384

            def embed(texts: List[str]) -> List[List[float]]:
                embs = _model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
                return [e.tolist() for e in embs]

            logger.info("Semantic store: using all-MiniLM-L6-v2 (local)")
            return embed
        except (ImportError, Exception) as e:
            logger.debug("Local embeddings unavailable: %s", e)
            return None

    async def _embed_openai_async(self, texts: List[str]) -> List[List[float]]:
        from openai import AsyncOpenAI
        from ..config import get_settings
        s = get_settings()
        client = AsyncOpenAI(api_key=s.openai_api_key or None)
        resp = await client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [d.embedding for d in resp.data]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self._embed_openai_async(texts)).result()
        return asyncio.run(self._embed_openai_async(texts))

    def _embed_tfidf(self, texts: List[str]) -> List[List[float]]:
        """Fallback: TF-IDF vectors (bag-of-words dimensionality)."""
        # Build vocab from all docs + query
        all_texts = [d.text for d in self._docs.values()] + texts
        vocab: Dict[str, int] = {}
        for t in all_texts:
            for w in re.findall(r"\b[a-z]{2,}\b", t.lower()):
                if w not in vocab:
                    vocab[w] = len(vocab)
        dim = max(len(vocab), 1)
        self._dim = dim
        result = []
        for text in texts:
            vec = [0.0] * dim
            tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
            counter = Counter(tokens)
            total = sum(counter.values()) or 1
            for word, count in counter.items():
                if word in vocab:
                    vec[vocab[word]] = count / total
            result.append(vec)
        return result

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1e-9
        nb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (na * nb)

    def add(self, doc: Document) -> None:
        if doc.embedding is None:
            doc.embedding = self._embed_fn([doc.text])[0]
        self._docs[doc.id] = doc
        if self._db_path:
            self._persist_doc(doc)

    def add_batch(self, docs: List[Document]) -> int:
        texts = [d.text for d in docs if d.embedding is None]
        if texts:
            embeddings = self._embed_fn(texts)
            idx = 0
            for d in docs:
                if d.embedding is None:
                    d.embedding = embeddings[idx]
                    idx += 1
        for d in docs:
            self._docs[d.id] = d
        if self._db_path:
            self._persist_all()
        return len(docs)

    def search(self, query: str, top_k: int = 5,
               filter_meta: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
        if not self._docs:
            return []
        q_emb = self._embed_fn([query])[0]
        results = []
        for doc in self._docs.values():
            if filter_meta and not all(doc.metadata.get(k) == v for k, v in filter_meta.items()):
                continue
            if doc.embedding is None:
                continue
            # Ensure compatible dimensions
            if len(q_emb) != len(doc.embedding):
                continue
            score = self._cosine_similarity(q_emb, doc.embedding)
            results.append((doc, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def remove(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)

    def clear(self) -> None:
        self._docs.clear()

    def __len__(self) -> int:
        return len(self._docs)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _persist_doc(self, doc: Document) -> None:
        import sqlite3
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embeddings "
            "(id TEXT PRIMARY KEY, text TEXT, metadata TEXT, embedding TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO embeddings (id, text, metadata, embedding) VALUES (?,?,?,?)",
            (doc.id, doc.text, json.dumps(doc.metadata),
             json.dumps(doc.embedding) if doc.embedding else "[]"),
        )
        conn.commit()
        conn.close()

    def _persist_all(self) -> None:
        if not self._db_path:
            return
        import sqlite3
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embeddings "
            "(id TEXT PRIMARY KEY, text TEXT, metadata TEXT, embedding TEXT)"
        )
        for doc in self._docs.values():
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (id, text, metadata, embedding) VALUES (?,?,?,?)",
                (doc.id, doc.text, json.dumps(doc.metadata),
                 json.dumps(doc.embedding) if doc.embedding else "[]"),
            )
        conn.commit()
        conn.close()

    def _load_from_db(self) -> None:
        if not self._db_path or not Path(self._db_path).exists():
            return
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS embeddings "
                "(id TEXT PRIMARY KEY, text TEXT, metadata TEXT, embedding TEXT)"
            )
            rows = conn.execute("SELECT id, text, metadata, embedding FROM embeddings").fetchall()
            for row in rows:
                emb = json.loads(row[3]) if row[3] else None
                self._docs[row[0]] = Document(
                    id=row[0], text=row[1],
                    metadata=json.loads(row[2]) if row[2] else {},
                    embedding=emb if emb else None,
                )
            conn.close()
            logger.info("Loaded %d documents from %s", len(self._docs), self._db_path)
        except Exception as e:
            logger.warning("Failed to load embeddings DB: %s", e)


# ── Singleton ──────────────────────────────────────────────────────────────────

_store: Optional[SemanticStore] = None


def get_semantic_store() -> SemanticStore:
    global _store
    if _store is None:
        _store = SemanticStore()
    return _store


def set_semantic_store(store: SemanticStore) -> None:
    global _store
    _store = store
