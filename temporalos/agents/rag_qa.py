"""RAG-powered Q&A agent — real retrieval-augmented generation.

Replaces mock synthesis in qa_agent.py with actual LLM-backed answers.
Uses SemanticStore for embedding-based retrieval, then LLM for synthesis.
Returns answers with exact timestamp citations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .semantic_store import Document, SemanticStore, get_semantic_store
from ..llm.router import get_llm

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    job_id: str
    segment_index: int
    timestamp: str
    topic: str
    risk_score: float
    excerpt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id, "segment_index": self.segment_index,
            "timestamp": self.timestamp, "topic": self.topic,
            "risk_score": self.risk_score, "excerpt": self.excerpt[:200],
        }


@dataclass
class QAAnswer:
    question: str
    answer: str
    citations: List[Citation] = field(default_factory=list)
    model: str = "mock"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question, "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "model": self.model,
        }


QA_SYSTEM = """\
You are an AI assistant that answers questions about recorded calls and meetings. \
You have access to relevant segments from the video library. Answer based ONLY on \
the provided context. If the context doesn't contain the answer, say so. \
Always reference specific timestamps in your answer.\
"""

QA_PROMPT = """\
Question: {question}

Relevant segments from the video library:
{context}

Answer the question based on the above context. Be specific and cite timestamps.\
"""


class RAGQAAgent:
    """Retrieval-Augmented Generation Q&A over video library."""

    def __init__(self, store: Optional[SemanticStore] = None, top_k: int = 5):
        self._store = store
        self.top_k = top_k

    def _get_store(self) -> SemanticStore:
        return self._store or get_semantic_store()

    def index_job(self, job_id: str, intel: Dict[str, Any]) -> int:
        """Index all segments from a processed job into the vector store."""
        store = self._get_store()
        segments = intel.get("segments", [])
        docs = []
        for i, seg in enumerate(segments):
            ext = seg.get("extraction", seg)
            ts = seg.get("timestamp_str", f"seg-{i}")
            text = (
                f"Topic: {ext.get('topic', 'general')}. "
                f"Transcript: {seg.get('transcript', '')}. "
                f"Objections: {', '.join(ext.get('objections', []))}. "
                f"Signals: {', '.join(ext.get('decision_signals', []))}."
            )
            docs.append(Document(
                id=f"{job_id}_seg{i}",
                text=text,
                metadata={
                    "job_id": job_id, "segment_index": i, "timestamp": ts,
                    "risk_score": ext.get("risk_score", 0.0),
                    "topic": ext.get("topic", "general"),
                    "objections": ext.get("objections", []),
                    "decision_signals": ext.get("decision_signals", []),
                    "transcript_excerpt": seg.get("transcript", "")[:300],
                },
            ))
        return store.add_batch(docs)

    def remove_job(self, job_id: str) -> None:
        store = self._get_store()
        to_remove = [k for k in store._docs if k.startswith(f"{job_id}_")]
        for doc_id in to_remove:
            store.remove(doc_id)

    async def ask(self, question: str,
                  filter_job_id: Optional[str] = None) -> QAAnswer:
        """Answer a question using RAG pipeline."""
        store = self._get_store()
        filter_meta = {"job_id": filter_job_id} if filter_job_id else None
        hits = store.search(question, top_k=self.top_k, filter_meta=filter_meta)

        if not hits:
            return QAAnswer(
                question=question,
                answer="No relevant video content found. Make sure videos are processed and indexed.",
                citations=[],
            )

        # Build context from retrieved segments
        context_blocks = []
        citations: List[Citation] = []
        for doc, score in hits:
            m = doc.metadata
            context_blocks.append(
                f"[{m.get('job_id', '?')} @ {m.get('timestamp', '?')} | "
                f"risk={round(m.get('risk_score', 0) * 100)}%]\n"
                f"Topic: {m.get('topic', 'general')}\n"
                f"Objections: {'; '.join(m.get('objections', [])) or 'none'}\n"
                f"Signals: {'; '.join(m.get('decision_signals', [])) or 'none'}\n"
                f"Transcript: {m.get('transcript_excerpt', '')[:200]}"
            )
            citations.append(Citation(
                job_id=m.get("job_id", ""),
                segment_index=m.get("segment_index", 0),
                timestamp=m.get("timestamp", ""),
                topic=m.get("topic", ""),
                risk_score=m.get("risk_score", 0.0),
                excerpt=m.get("transcript_excerpt", ""),
            ))

        context = "\n---\n".join(context_blocks)
        prompt = QA_PROMPT.format(question=question, context=context)

        llm = get_llm()
        try:
            resp = await llm.complete(
                prompt=prompt, system=QA_SYSTEM,
                temperature=0.1, max_tokens=1024,
            )
            answer_text = resp.text.strip()
            model_name = resp.model
        except Exception as e:
            logger.warning("LLM Q&A failed: %s, using context summary", e)
            answer_text = self._fallback_answer(question, hits)
            model_name = "fallback"

        return QAAnswer(
            question=question,
            answer=answer_text,
            citations=citations,
            model=model_name,
        )

    def _fallback_answer(self, question: str, hits) -> str:
        """Rule-based fallback when LLM fails."""
        topics = set()
        objections = []
        for doc, _ in hits:
            m = doc.metadata
            topics.add(m.get("topic", "general"))
            objections.extend(m.get("objections", []))
        unique_obj = list(dict.fromkeys(objections))[:5]
        return (
            f"Found {len(hits)} relevant segment(s) covering: {', '.join(topics)}. "
            + (f"Key objections: {'; '.join(unique_obj)}." if unique_obj else "")
        )

    @property
    def index_size(self) -> int:
        return len(self._get_store())


# Singleton
_agent: Optional[RAGQAAgent] = None


def get_rag_qa_agent() -> RAGQAAgent:
    global _agent
    if _agent is None:
        _agent = RAGQAAgent()
    return _agent
