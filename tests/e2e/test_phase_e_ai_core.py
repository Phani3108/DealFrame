"""Phase E E2E test — AI-Native Core.

Tests all Phase E modules:
  1. LLM router (mock provider)
  2. LLM extraction router
  3. Semantic vector store
  4. AI summarization engine
  5. RAG Q&A agent
  6. Smart coaching (LLM narrative)
  7. NER knowledge graph
  8. AI meeting prep
  9. Persistent state models
  10. pyannote diarizer (fallback path)
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_intel(risk: float = 0.5, topic: str = "pricing",
                objections: List[str] | None = None,
                signals: List[str] | None = None) -> Dict[str, Any]:
    return {
        "overall_risk_score": risk,
        "duration_ms": 60_000,
        "segments": [
            {
                "timestamp_str": "00:00",
                "timestamp_ms": 0,
                "transcript": f"Discussion about {topic} with Acme Corp. John mentioned budget concerns.",
                "extraction": {
                    "topic": topic,
                    "risk": "high" if risk > 0.6 else "medium" if risk > 0.3 else "low",
                    "risk_score": risk,
                    "objections": objections or ["pricing too high"],
                    "decision_signals": signals or ["send proposal"],
                    "sentiment": "negative" if risk > 0.6 else "neutral",
                    "confidence": 0.8,
                },
            },
            {
                "timestamp_str": "00:30",
                "timestamp_ms": 30_000,
                "transcript": "Let's schedule a follow-up meeting with Sarah about the enterprise plan.",
                "extraction": {
                    "topic": "next_steps",
                    "risk": "low",
                    "risk_score": 0.1,
                    "objections": [],
                    "decision_signals": ["schedule follow-up", "evaluate timeline"],
                    "sentiment": "positive",
                    "confidence": 0.9,
                },
            },
        ],
    }


def _run(coro):
    """Run an async function synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ── 1. LLM Router ─────────────────────────────────────────────────────────────

class TestLLMRouter:
    def test_mock_provider_complete(self):
        from temporalos.llm.router import MockLLMProvider
        provider = MockLLMProvider()
        resp = _run(provider.complete("Hello"))
        assert resp.text
        assert resp.model == "mock"
        assert resp.latency_ms >= 0

    def test_mock_provider_json(self):
        from temporalos.llm.router import MockLLMProvider
        provider = MockLLMProvider()
        data = _run(provider.complete_json("Extract fields"))
        assert isinstance(data, dict)
        assert "topic" in data

    def test_mock_provider_stream(self):
        from temporalos.llm.router import MockLLMProvider
        provider = MockLLMProvider(default_response="Hello world test")

        async def collect():
            chunks = []
            async for chunk in provider.stream("Hello"):
                chunks.append(chunk)
            return chunks

        chunks = _run(collect())
        assert len(chunks) > 0
        assert "".join(chunks).strip()

    def test_set_and_get_llm(self):
        from temporalos.llm.router import MockLLMProvider, set_llm, get_llm
        mock = MockLLMProvider(default_response="injected")
        set_llm(mock)
        assert get_llm() is mock
        # Reset for other tests
        set_llm(MockLLMProvider())

    def test_llm_response_fields(self):
        from temporalos.llm.router import LLMResponse
        r = LLMResponse(text="hi", model="test", latency_ms=42,
                        prompt_tokens=10, completion_tokens=5)
        assert r.prompt_tokens == 10
        assert r.completion_tokens == 5


# ── 2. LLM Extraction Router ──────────────────────────────────────────────────

class TestLLMExtractionRouter:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        set_llm(MockLLMProvider())

    def test_extract_returns_extraction_result(self):
        from temporalos.extraction.router import LLMExtractionRouter
        from temporalos.core.types import AlignedSegment, Word

        router = LLMExtractionRouter()
        words = [
            Word(text="We", start_ms=0, end_ms=200),
            Word(text="need", start_ms=200, end_ms=400),
            Word(text="to", start_ms=400, end_ms=500),
            Word(text="discuss", start_ms=500, end_ms=800),
            Word(text="pricing", start_ms=800, end_ms=1200),
        ]
        segment = AlignedSegment(
            timestamp_ms=0, frame=None, words=words,
        )
        result = router.extract(segment)
        assert result is not None
        assert hasattr(result, "topic")
        assert hasattr(result, "risk_score")
        assert 0.0 <= result.risk_score <= 1.0

    def test_extraction_router_singleton(self):
        from temporalos.extraction.router import get_extraction_router
        r1 = get_extraction_router()
        r2 = get_extraction_router()
        assert r1 is r2


# ── 3. Semantic Vector Store ──────────────────────────────────────────────────

class TestSemanticVectorStore:
    def test_add_and_search(self):
        from temporalos.agents.semantic_store import Document, SemanticStore, set_semantic_store
        store = SemanticStore(embed_model="tfidf")
        set_semantic_store(store)
        store.add(Document(id="d1", text="pricing discussion about enterprise tier cost budget"))
        store.add(Document(id="d2", text="technical integration with APIs and architecture"))
        store.add(Document(id="d3", text="contract renewal and budget pricing"))

        results = store.search("pricing budget cost", top_k=2)
        assert len(results) > 0
        assert len(results) <= 2

    def test_filter_meta(self):
        from temporalos.agents.semantic_store import Document, SemanticStore
        store = SemanticStore(embed_model="tfidf")
        store.add(Document(id="j1_s0", text="pricing talk", metadata={"job_id": "j1"}))
        store.add(Document(id="j2_s0", text="pricing talk", metadata={"job_id": "j2"}))

        results = store.search("pricing", filter_meta={"job_id": "j1"})
        assert all(d.metadata.get("job_id") == "j1" for d, _ in results)

    def test_remove_and_clear(self):
        from temporalos.agents.semantic_store import Document, SemanticStore
        store = SemanticStore(embed_model="tfidf")
        store.add(Document(id="d1", text="test"))
        assert len(store) == 1
        store.remove("d1")
        assert len(store) == 0

    def test_add_batch(self):
        from temporalos.agents.semantic_store import Document, SemanticStore
        store = SemanticStore(embed_model="tfidf")
        docs = [Document(id=f"d{i}", text=f"doc {i}") for i in range(5)]
        count = store.add_batch(docs)
        assert count == 5
        assert len(store) == 5


# ── 4. AI Summarization ───────────────────────────────────────────────────────

class TestAISummarization:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        set_llm(MockLLMProvider())

    def test_generate_summary(self):
        from temporalos.summarization.ai_engine import generate_summary
        intel = _make_intel()
        result = _run(generate_summary(intel, "executive"))
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) > 0
        assert result["summary_type"] == "executive"

    def test_fallback_summary(self):
        from temporalos.summarization.ai_engine import _fallback_summary
        intel = _make_intel()
        result = _fallback_summary(intel, "executive")
        assert isinstance(result, str)
        assert len(result) > 0


# ── 5. RAG Q&A Agent ──────────────────────────────────────────────────────────

class TestRAGQAAgent:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        from temporalos.agents.semantic_store import SemanticStore, set_semantic_store
        set_llm(MockLLMProvider(default_response="Based on the calls, pricing was discussed."))
        set_semantic_store(SemanticStore(embed_model="tfidf"))

    def test_index_and_ask(self):
        from temporalos.agents.rag_qa import RAGQAAgent
        from temporalos.agents.semantic_store import SemanticStore
        store = SemanticStore(embed_model="tfidf")
        agent = RAGQAAgent(store=store)
        intel = _make_intel()
        count = agent.index_job("job1", intel)
        assert count == 2
        assert agent.index_size == 2

        answer = _run(agent.ask("What pricing objections came up?"))
        assert answer.question
        assert len(answer.answer) > 0
        # With TF-IDF, search finds docs by word overlap
        assert answer.model in ("mock", "fallback")

    def test_empty_index_returns_no_content(self):
        from temporalos.agents.rag_qa import RAGQAAgent
        from temporalos.agents.semantic_store import SemanticStore
        store = SemanticStore(embed_model="tfidf")
        agent = RAGQAAgent(store=store)
        answer = _run(agent.ask("anything"))
        assert "No relevant video content" in answer.answer

    def test_remove_job(self):
        from temporalos.agents.rag_qa import RAGQAAgent
        from temporalos.agents.semantic_store import SemanticStore
        store = SemanticStore(embed_model="tfidf")
        agent = RAGQAAgent(store=store)
        agent.index_job("job1", _make_intel())
        assert agent.index_size > 0
        agent.remove_job("job1")
        assert agent.index_size == 0


# ── 6. Smart Coaching ─────────────────────────────────────────────────────────

class TestSmartCoaching:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        set_llm(MockLLMProvider(default_response="Great job on discovery questions."))

    def test_smart_coaching_generates_narrative(self):
        from temporalos.agents.coaching import CoachingEngine
        from temporalos.agents.smart_coaching import smart_coaching

        engine = CoachingEngine()
        engine.record_call("rep1", "job1", _make_intel(), speaker_label="SPEAKER_A")
        engine.record_call("rep1", "job2", _make_intel(risk=0.3), speaker_label="SPEAKER_A")

        result = _run(smart_coaching("rep1", engine=engine))
        assert result is not None
        assert "narrative" in result
        assert len(result["narrative"]) > 0
        assert result["rep_id"] == "rep1"

    def test_no_data_returns_none(self):
        from temporalos.agents.coaching import CoachingEngine
        from temporalos.agents.smart_coaching import smart_coaching

        engine = CoachingEngine()
        result = _run(smart_coaching("nobody", engine=engine))
        assert result is None


# ── 7. NER Knowledge Graph ────────────────────────────────────────────────────

class TestNERKnowledgeGraph:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        # Mock returns entity array as JSON
        import json
        entities = [
            {"entity": "Acme Corp", "type": "company"},
            {"entity": "pricing", "type": "topic"},
            {"entity": "John", "type": "person"},
        ]
        set_llm(MockLLMProvider(default_response=json.dumps(entities)))

    def test_fallback_ner(self):
        from temporalos.agents.ner_graph import _fallback_ner
        seg = {"extraction": {"topic": "pricing", "objections": ["too expensive"]}}
        entities = _fallback_ner(seg)
        assert len(entities) >= 1
        types = [t for _, t in entities]
        assert "topic" in types

    def test_add_video_with_ner(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        from temporalos.agents.ner_graph import add_video_with_ner

        kg = KnowledgeGraph()
        intel = _make_intel()
        count = _run(add_video_with_ner(kg, "job1", intel))
        # With mock LLM returning 3 entities x 2 segments = ~6 entities
        assert count > 0
        assert kg.stats["nodes"] > 0


# ── 8. AI Meeting Prep ────────────────────────────────────────────────────────

class TestAIMeetingPrep:
    def setup_method(self):
        from temporalos.llm.router import MockLLMProvider, set_llm
        set_llm(MockLLMProvider(default_response="Prepare to discuss pricing."))

    def test_generate_ai_brief(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        from temporalos.agents.ai_meeting_prep import generate_ai_brief

        agent = MeetingPrepAgent()
        agent.index_job("job1", _make_intel(), company="Acme", contact="John")

        result = _run(generate_ai_brief("Acme", "John", agent=agent))
        assert "ai_brief" in result
        assert len(result["ai_brief"]) > 0
        assert result["company"] == "Acme"

    def test_new_company_brief(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        from temporalos.agents.ai_meeting_prep import generate_ai_brief

        agent = MeetingPrepAgent()
        result = _run(generate_ai_brief("NewCo", agent=agent))
        assert result["prior_calls"] == 0


# ── 9. Persistent State Models ────────────────────────────────────────────────

class TestPersistentState:
    def test_new_models_importable(self):
        from temporalos.db.models import (
            RiskEvent, KGNodeRecord, KGEdgeRecord,
            SummaryCache, CoachingRecord, SpeakerLabel,
            Tenant, User, AuditLog, Notification,
        )
        # Verify table names
        assert RiskEvent.__tablename__ == "risk_events"
        assert KGNodeRecord.__tablename__ == "kg_nodes"
        assert SummaryCache.__tablename__ == "summary_cache"
        assert Tenant.__tablename__ == "tenants"
        assert User.__tablename__ == "users"
        assert AuditLog.__tablename__ == "audit_logs"
        assert Notification.__tablename__ == "notifications"


# ── 10. pyannote Diarizer ─────────────────────────────────────────────────────

class TestDiarizer:
    def test_mock_diarizer_still_works(self):
        from temporalos.diarization.diarizer import MockDiarizer
        from temporalos.core.types import Word

        words = [
            Word(text="Hello", start_ms=0, end_ms=500),
            Word(text="how", start_ms=600, end_ms=800),
            Word(text="are", start_ms=2500, end_ms=2700),
            Word(text="you", start_ms=2800, end_ms=3000),
        ]
        d = MockDiarizer(pause_threshold_ms=1500)
        labeled = d.diarize(words)
        assert len(labeled) == 4
        assert labeled[0].speaker == "SPEAKER_A"
        # Gap at 2500-800=1700ms > 1500ms → speaker change
        assert labeled[2].speaker == "SPEAKER_B"

    def test_get_segments(self):
        from temporalos.diarization.diarizer import MockDiarizer
        from temporalos.core.types import Word

        words = [
            Word(text="Hi", start_ms=0, end_ms=500),
            Word(text="there", start_ms=600, end_ms=800),
            Word(text="Sure", start_ms=3000, end_ms=3200),
        ]
        d = MockDiarizer(pause_threshold_ms=1500)
        segs = d.get_segments(words)
        assert len(segs) == 2
        assert segs[0].speaker == "SPEAKER_A"
        assert segs[1].speaker == "SPEAKER_B"

    def test_pyannote_diarizer_importable(self):
        from temporalos.diarization.diarizer import PyAnnoteDiarizer
        d = PyAnnoteDiarizer(hf_token="test")
        assert d._hf_token == "test"

    def test_factory_falls_back_to_mock(self):
        from temporalos.diarization.diarizer import get_diarizer, MockDiarizer
        d = get_diarizer(use_pyannote=True)  # pyannote likely not installed
        assert isinstance(d, MockDiarizer)
