"""LlamaIndex reader for TemporalOS.

Loads processed video jobs as LlamaIndex Documents, making the entire
video library queryable via any LlamaIndex RAG pipeline.

Usage:
    from temporalos.integrations.llamaindex_reader import TemporalOSReader
    reader = TemporalOSReader(base_url="http://localhost:8000")
    docs = reader.load_data(query="pricing objections", limit=20)
    # Pass docs to a VectorStoreIndex or any other LlamaIndex index
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TemporalOSDocument:
    """Minimal Document compatible with LlamaIndex Document API."""

    def __init__(self, text: str, doc_id: str,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        self.text = text
        self.doc_id = doc_id
        self.metadata = metadata or {}
        # LlamaIndex usually expects `id_` and `extra_info`
        self.id_ = doc_id
        self.extra_info = self.metadata


class TemporalOSReader:
    """LlamaIndex-compatible reader that fetches video intelligence from TemporalOS.

    Yields one Document per *segment* (not per job), giving the index dense,
    timestamped chunks to retrieve from.

    If `llama_index` is installed the reader registers itself as a proper
    BaseReader; otherwise it falls back gracefully.
    """

    def __init__(self, base_url: str = "http://localhost:8000",
                 api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    # ------------------------------------------------------------------
    # Core data loading
    # ------------------------------------------------------------------

    def load_data(self, query: str = "", limit: int = 50,
                  job_ids: Optional[List[str]] = None) -> List[TemporalOSDocument]:
        """Load Documents from TemporalOS for a given query or list of jobs."""
        from temporalos.integrations.base import http_get

        if job_ids:
            docs = []
            for jid in job_ids:
                docs.extend(self._load_job(jid))
            return docs

        # Search endpoint
        params: Dict[str, str] = {"limit": str(limit)}
        if query:
            params["q"] = query

        status, resp = http_get(
            f"{self.base_url}/api/v1/search",
            params=params,
            headers=self._headers(),
        )
        results = resp.get("results", [])
        docs: List[TemporalOSDocument] = []
        for hit in results:
            docs.extend(self._job_to_docs(hit.get("job_id", ""), hit))
        return docs

    def _load_job(self, job_id: str) -> List[TemporalOSDocument]:
        from temporalos.integrations.base import http_get
        status, resp = http_get(
            f"{self.base_url}/api/v1/intelligence/{job_id}",
            headers=self._headers(),
        )
        if status != 200:
            logger.warning("Could not load job %s: %s", job_id, status)
            return []
        return self._job_to_docs(job_id, resp)

    def _job_to_docs(self, job_id: str,
                     job_data: Dict[str, Any]) -> List[TemporalOSDocument]:
        """Convert a job's segments to individual LlamaIndex Documents."""
        docs: List[TemporalOSDocument] = []
        segments = job_data.get("segments", [])

        for i, seg in enumerate(segments):
            ext = seg.get("extraction", seg)
            ts = seg.get("timestamp_str", seg.get("timestamp", f"seg-{i}"))
            text = "\n".join([
                f"[Job {job_id} @ {ts}]",
                f"Topic: {ext.get('topic', 'general')}",
                f"Risk: {ext.get('risk', 'low')} ({round(ext.get('risk_score', 0) * 100)}%)",
                f"Objections: {'; '.join(ext.get('objections', [])) or 'None'}",
                f"Decision signals: {'; '.join(ext.get('decision_signals', [])) or 'None'}",
                f"Transcript: {seg.get('transcript', '')}",
            ])
            doc = TemporalOSDocument(
                text=text,
                doc_id=f"{job_id}_seg{i}",
                metadata={
                    "job_id": job_id,
                    "segment_index": i,
                    "timestamp": ts,
                    "risk_score": ext.get("risk_score", 0),
                    "topic": ext.get("topic", "general"),
                },
            )
            docs.append(doc)

        return docs

    # ------------------------------------------------------------------
    # LlamaIndex integration (optional)
    # ------------------------------------------------------------------

    @classmethod
    def as_llama_reader(cls, base_url: str = "http://localhost:8000",
                        api_key: str = "") -> "TemporalOSReader":
        """Return self wrapped as a proper LlamaIndex BaseReader if available."""
        try:
            from llama_index.core.readers.base import BaseReader

            class _LlamaReader(BaseReader, cls):  # type: ignore[misc]
                def load_data(self, query: str = "", limit: int = 50,
                              job_ids: Optional[List[str]] = None):
                    raw = super().load_data(query=query, limit=limit, job_ids=job_ids)
                    # Convert to real llama_index Document
                    from llama_index.core import Document
                    return [Document(text=d.text, doc_id=d.doc_id,
                                     extra_info=d.metadata) for d in raw]

            return _LlamaReader(base_url=base_url, api_key=api_key)
        except ImportError:
            return cls(base_url=base_url, api_key=api_key)
