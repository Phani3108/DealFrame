"""Phase C E2E test — Intelligence Agents.

Tests all 5 new agents:
  1. Video Q&A Agent (TF-IDF RAG)
  2. Deal Risk Agent (threshold + spike alerts)
  3. Coaching Engine (per-rep metrics)
  4. Knowledge Graph (entity co-occurrence)
  5. Meeting Prep Agent (historical context brief)

Plus Batch Processing (submit → poll → result).
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_intel(risk: float = 0.5, topic: str = "pricing",
                objections: List[str] = None,
                signals: List[str] = None) -> Dict[str, Any]:
    return {
        "overall_risk_score": risk,
        "duration_ms": 60_000,
        "segments": [
            {
                "timestamp_str": "00:00",
                "timestamp_ms": 0,
                "transcript": f"Discussion about {topic}.",
                "extraction": {
                    "topic": topic,
                    "risk": "high" if risk > 0.6 else "medium" if risk > 0.3 else "low",
                    "risk_score": risk,
                    "objections": objections or ["pricing too high"],
                    "decision_signals": signals or ["send proposal"],
                },
            },
            {
                "timestamp_str": "00:30",
                "timestamp_ms": 30_000,
                "transcript": "Let's schedule a follow-up.",
                "extraction": {
                    "topic": "next_steps",
                    "risk": "low",
                    "risk_score": 0.1,
                    "objections": [],
                    "decision_signals": ["schedule follow-up", "evaluate timeline"],
                },
            },
        ],
    }


# ── 1. Video Q&A Agent ────────────────────────────────────────────────────────

class TestVideoQAAgent:
    def test_index_and_ask(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        intel = _make_intel(0.75, "pricing", ["too expensive", "competitor pricing"], ["send proposal"])
        agent.index_job("job-001", intel)
        assert agent.index_size == 2  # 2 segments

        answer = agent.ask("What objections came up?")
        assert answer.question == "What objections came up?"
        assert len(answer.answer) > 0
        assert len(answer.citations) > 0

    def test_ask_returns_citations(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        agent.index_job("job-002", _make_intel(0.8, "security", ["no SOC2 cert"]))
        answer = agent.ask("security certification")
        assert any(c.job_id == "job-002" for c in answer.citations)

    def test_ask_empty_index(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        answer = agent.ask("anything")
        assert "not found" in answer.answer.lower() or "no relevant" in answer.answer.lower()

    def test_filter_by_job_id(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        agent.index_job("job-A", _make_intel(0.8, "pricing"))
        agent.index_job("job-B", _make_intel(0.2, "onboarding"))
        answer = agent.ask("pricing", filter_job_id="job-A")
        assert all(c.job_id == "job-A" for c in answer.citations)

    def test_answer_to_dict_schema(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        agent.index_job("job-x", _make_intel())
        d = agent.ask("objections").to_dict()
        assert all(k in d for k in ("question", "answer", "citations", "model"))

    def test_remove_job(self):
        from temporalos.agents.qa_agent import VideoQAAgent
        agent = VideoQAAgent()
        agent.index_job("job-del", _make_intel())
        assert agent.index_size == 2
        agent.remove_job("job-del")
        assert agent.index_size == 0


# ── 2. Deal Risk Agent ────────────────────────────────────────────────────────

class TestDealRiskAgent:
    def test_threshold_alert_fires(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        alerts = agent.record_job("job-001", _make_intel(0.3), "Acme", "deal-1")
        assert len(alerts) == 0  # below threshold

        alerts2 = agent.record_job("job-002", _make_intel(0.72), "Acme", "deal-1")
        alert_types = {a.alert_type for a in alerts2}
        assert "threshold_crossed" in alert_types

    def test_risk_spike_alert(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        agent.record_job("j1", _make_intel(0.2), "Beta", "d1")
        alerts = agent.record_job("j2", _make_intel(0.7), "Beta", "d1")
        alert_types = {a.alert_type for a in alerts}
        assert "risk_spike" in alert_types

    def test_persistent_high_alert(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        for i in range(3):
            agent.record_job(f"j{i}", _make_intel(0.75), "Gamma", "d1")
        alerts = agent.run_sweep()
        assert any(a.company == "Gamma" for a in alerts)

    def test_run_sweep_empty(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        assert agent.run_sweep() == []

    def test_list_deals(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        agent.record_job("j1", _make_intel(0.8), "Delta", "d1")
        agent.record_job("j2", _make_intel(0.4), "Epsilon", "d2")
        deals = agent.list_deals()
        assert len(deals) == 2
        # Sorted by descending risk
        assert deals[0]["latest_risk"] >= deals[1]["latest_risk"]

    def test_alert_to_dict(self):
        from temporalos.agents.risk_agent import DealRiskAgent
        agent = DealRiskAgent()
        alerts = agent.record_job("j1", _make_intel(0.7), "Zeta", "d1")
        if alerts:
            d = alerts[0].to_dict()
            assert all(k in d for k in ("job_id", "alert_type", "risk_score", "message"))


# ── 3. Coaching Engine ────────────────────────────────────────────────────────

class TestCoachingEngine:
    def test_generate_coaching_card(self):
        from temporalos.agents.coaching import CoachingEngine
        engine = CoachingEngine()
        for i in range(3):
            engine.record_call("rep-alice", f"job-{i}", _make_intel(0.4 + i * 0.1),
                               speaker_label="SPEAKER_A")
        card = engine.generate_coaching_card("rep-alice")
        assert card is not None
        assert card.rep_id == "rep-alice"
        assert card.calls_analyzed == 3
        assert len(card.dimensions) == 5
        assert 0.0 <= card.overall_score <= 1.0

    def test_coaching_card_grade(self):
        from temporalos.agents.coaching import CoachingEngine
        engine = CoachingEngine()
        engine.record_call("rep-bob", "j1", _make_intel())
        card = engine.generate_coaching_card("rep-bob")
        assert card.to_dict()["grade"] in ("A", "B", "C", "D")

    def test_no_data_returns_none(self):
        from temporalos.agents.coaching import CoachingEngine
        engine = CoachingEngine()
        assert engine.generate_coaching_card("unknown-rep") is None

    def test_list_reps(self):
        from temporalos.agents.coaching import CoachingEngine
        engine = CoachingEngine()
        engine.record_call("r1", "j1", _make_intel())
        engine.record_call("r2", "j2", _make_intel())
        assert "r1" in engine.list_reps()
        assert "r2" in engine.list_reps()

    def test_card_to_dict_schema(self):
        from temporalos.agents.coaching import CoachingEngine
        engine = CoachingEngine()
        engine.record_call("r3", "j3", _make_intel())
        d = engine.generate_coaching_card("r3").to_dict()
        assert all(k in d for k in ("rep_id", "calls_analyzed", "overall_score",
                                     "grade", "dimensions", "strengths", "improvements"))


# ── 4. Knowledge Graph ────────────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_add_video_and_query(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        intel = _make_intel(0.7, "pricing", ["pricing too high", "contract concerns"])
        n = kg.add_video("job-001", intel)
        assert n > 0
        result = kg.query("pricing")
        assert len(result["nodes"]) > 0

    def test_top_entities(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_video("j1", _make_intel(0.6, "pricing"))
        kg.add_video("j2", _make_intel(0.4, "pricing"))
        kg.add_video("j3", _make_intel(0.5, "onboarding"))
        top = kg.top_entities(entity_type="topic")
        assert len(top) > 0
        assert top[0]["frequency"] >= 1

    def test_get_relationships(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_video("j1", _make_intel(0.8, "demo", ["needs demo", "timeline concern"]))
        rels = kg.get_relationships("demo")
        assert isinstance(rels, list)

    def test_export_json(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_video("j1", _make_intel())
        exported = kg.export_json()
        assert "nodes" in exported and "edges" in exported
        assert "stats" in exported
        assert exported["stats"]["node_count"] > 0

    def test_stats(self):
        from temporalos.agents.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        assert kg.stats == {"nodes": 0, "edges": 0}
        kg.add_video("j1", _make_intel())
        assert kg.stats["nodes"] > 0


# ── 5. Meeting Prep Agent ─────────────────────────────────────────────────────

class TestMeetingPrepAgent:
    def test_generate_brief_with_history(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        agent = MeetingPrepAgent()
        for i in range(2):
            agent.index_job(f"j{i}", _make_intel(0.5 + i * 0.15, "pricing"), "AcmeCorp", "John")
        brief = agent.generate_brief("AcmeCorp", "John")
        assert brief.company == "AcmeCorp"
        assert brief.prior_calls == 2
        assert len(brief.talking_points) > 0

    def test_generate_brief_new_company(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        agent = MeetingPrepAgent()
        brief = agent.generate_brief("NewProspect Inc.", "Jane Doe")
        assert brief.prior_calls == 0
        assert brief.risk_trajectory == "new"
        assert len(brief.talking_points) > 0
        assert "No prior history" in brief.watch_outs[0]

    def test_risk_trajectory_rising(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        agent = MeetingPrepAgent()
        agent.index_job("j1", _make_intel(0.3), "RiskyDeal", "")
        agent.index_job("j2", _make_intel(0.7), "RiskyDeal", "")
        brief = agent.generate_brief("RiskyDeal")
        assert brief.risk_trajectory == "rising"

    def test_brief_to_dict_schema(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        agent = MeetingPrepAgent()
        d = agent.generate_brief("AnyCompany").to_dict()
        assert all(k in d for k in ("company", "prior_calls", "risk_trajectory",
                                     "talking_points", "watch_outs", "open_objections"))

    def test_indexed_companies(self):
        from temporalos.agents.meeting_prep import MeetingPrepAgent
        agent = MeetingPrepAgent()
        agent.index_job("j1", _make_intel(), "Alpha Corp")
        agent.index_job("j2", _make_intel(), "Beta LLC")
        assert "alpha corp" in agent.indexed_companies
        assert "beta llc" in agent.indexed_companies


# ── 6. Batch Processing ───────────────────────────────────────────────────────

class TestBatchProcessing:
    @pytest.mark.asyncio
    async def test_submit_and_process(self):
        import uuid
        from temporalos.batch.models import BatchItem, BatchJob, BatchStatus
        from temporalos.batch.queue import BatchQueue
        from temporalos.batch.processor import BatchProcessor

        queue = BatchQueue()
        processor = BatchProcessor(queue=queue)

        job = BatchJob(
            items=[
                BatchItem(item_id=uuid.uuid4().hex, url="https://example.com/video1.mp4"),
                BatchItem(item_id=uuid.uuid4().hex, url="https://example.com/video2.mp4"),
            ],
        )
        bid = await queue.submit(job)
        assert bid == job.batch_id

        finished = await processor.run_once()
        assert finished is not None
        assert finished.status in (BatchStatus.COMPLETED, BatchStatus.PARTIAL)
        assert finished.completed_count == 2

    @pytest.mark.asyncio
    async def test_batch_progress(self):
        import uuid
        from temporalos.batch.models import BatchItem, BatchJob
        from temporalos.batch.queue import BatchQueue
        from temporalos.batch.processor import BatchProcessor

        queue = BatchQueue()
        processor = BatchProcessor(queue=queue)

        job = BatchJob(items=[
            BatchItem(item_id=uuid.uuid4().hex, url=f"https://example.com/v{i}.mp4")
            for i in range(5)
        ])
        await queue.submit(job)
        await processor.run_once()

        assert job.total == 5
        assert job.progress_pct == 100.0

    def test_batch_to_dict_schema(self):
        import uuid
        from temporalos.batch.models import BatchItem, BatchJob
        job = BatchJob(items=[BatchItem(item_id="i1", url="https://x.com/v.mp4")])
        d = job.to_dict()
        assert all(k in d for k in ("batch_id", "status", "total", "completed",
                                     "failed", "progress_pct", "items"))
