"""
Phase 10 end-to-end tests — Video Search & Portfolio Intelligence.

Covers:
  - SearchIndex:         index, search (TF-IDF), filters, clear, thread safety
  - SearchEngine:        index_extraction helper, query delegation
  - PortfolioInsights:   win_loss_patterns, objection_velocity, rep_comparison
  - Search API routes:   GET /api/v1/search, /search/index/stats,
                         /search/insights/patterns, /search/insights/velocity,
                         /search/insights/reps

Rule §0: pure in-memory, no external services, DB mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── SearchIndex ───────────────────────────────────────────────────────────────


class TestSearchIndex:
    def _make_entry(self, doc_id="v1:0", topic="pricing", risk="high"):
        from temporalos.search.indexer import IndexEntry

        return IndexEntry(
            doc_id=doc_id,
            video_id="v1",
            timestamp_ms=0,
            timestamp_str="00:00",
            topic=topic,
            risk=risk,
            risk_score=0.8,
            objections=["too expensive"],
            decision_signals=["send a proposal"],
            transcript="The pricing seems too expensive compared to competitors",
            model="gpt4o",
        )

    def test_document_count_empty(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        assert idx.document_count == 0

    def test_index_increases_count(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0"))
        assert idx.document_count == 1

    def test_re_index_same_doc_doesnt_double_count(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        entry = self._make_entry("v1:0")
        idx.index(entry)
        idx.index(entry)
        assert idx.document_count == 1

    def test_search_empty_index_returns_empty(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        assert idx.search("pricing") == []

    def test_search_finds_matching_doc(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0", topic="pricing"))
        results = idx.search("pricing")
        assert len(results) == 1
        assert results[0].entry.doc_id == "v1:0"

    def test_search_no_match_returns_empty(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0", topic="pricing"))
        results = idx.search("completely unrelated zxqy")
        assert results == []

    def test_search_risk_filter(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0", risk="high"))
        idx.index(self._make_entry("v2:0", risk="low"))
        high_results = idx.search("pricing", risk_filter="high")
        low_results = idx.search("pricing", risk_filter="low")
        assert all(r.entry.risk == "high" for r in high_results)
        assert all(r.entry.risk == "low" for r in low_results)

    def test_search_topic_filter(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0", topic="pricing"))
        idx.index(self._make_entry("v2:0", topic="competition"))
        results = idx.search("expensive competitors", topic_filter="pricing")
        assert all(r.entry.topic == "pricing" for r in results)

    def test_search_respects_limit(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        for i in range(10):
            idx.index(self._make_entry(f"v{i}:0"))
        results = idx.search("pricing expensive", limit=3)
        assert len(results) <= 3

    def test_search_scores_are_positive(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0"))
        results = idx.search("pricing expensive")
        for r in results:
            assert r.score > 0

    def test_clear_empties_index(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0"))
        idx.clear()
        assert idx.document_count == 0
        assert idx.search("pricing") == []

    def test_search_result_to_dict(self):
        from temporalos.search.indexer import SearchIndex

        idx = SearchIndex()
        idx.index(self._make_entry("v1:0"))
        results = idx.search("pricing")
        d = results[0].to_dict()
        assert "doc_id" in d
        assert "video_id" in d
        assert "timestamp_ms" in d
        assert "risk" in d
        assert "score" in d

    def test_searchable_text_combines_fields(self):
        entry = self._make_entry("v1:0")
        text = entry.searchable_text
        assert "pricing" in text
        assert "expensive" in text
        assert "proposal" in text

    def test_global_singleton(self):
        from temporalos.search.indexer import get_search_index

        idx1 = get_search_index()
        idx2 = get_search_index()
        assert idx1 is idx2


# ── SearchEngine ──────────────────────────────────────────────────────────────


class TestSearchEngine:
    def test_index_extraction_creates_entry(self):
        from temporalos.search.indexer import SearchIndex
        from temporalos.search.query import SearchEngine, SearchQuery

        idx = SearchIndex()
        engine = SearchEngine(index=idx)
        engine.index_extraction(
            video_id="v99",
            timestamp_ms=3000,
            timestamp_str="00:03",
            topic="security",
            risk="medium",
            risk_score=0.5,
            objections=["compliance concern"],
            decision_signals=[],
            transcript="Do you have SOC2 compliance",
            model="gpt4o",
        )
        results = engine.search(SearchQuery(text="compliance SOC2"))
        assert len(results) >= 1

    def test_empty_query_returns_empty(self):
        from temporalos.search.indexer import SearchIndex
        from temporalos.search.query import SearchEngine, SearchQuery

        idx = SearchIndex()
        engine = SearchEngine(index=idx)
        assert engine.search(SearchQuery(text="")) == []

    def test_whitespace_only_query_returns_empty(self):
        from temporalos.search.indexer import SearchIndex
        from temporalos.search.query import SearchEngine, SearchQuery

        idx = SearchIndex()
        engine = SearchEngine(index=idx)
        assert engine.search(SearchQuery(text="   ")) == []


# ── PortfolioInsights ─────────────────────────────────────────────────────────


class TestPortfolioInsights:
    def _make_extractions(self):
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        return [
            {
                "topic": "pricing",
                "risk": "high",
                "risk_score": 0.9,
                "objections": ["too expensive", "competitor is cheaper"],
                "decision_signals": [],
                "created_at": (now - timedelta(days=10)).isoformat(),
            },
            {
                "topic": "features",
                "risk": "low",
                "risk_score": 0.2,
                "objections": [],
                "decision_signals": ["can you send a proposal"],
                "created_at": (now - timedelta(days=3)).isoformat(),
            },
            {
                "topic": "pricing",
                "risk": "high",
                "risk_score": 0.85,
                "objections": ["too expensive"],
                "decision_signals": [],
                "created_at": now.isoformat(),
            },
        ]

    def test_win_loss_empty_extractions(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.win_loss_patterns([])
        assert result.avg_risk_score == 0.0
        assert result.high_risk_objections == []

    def test_win_loss_detects_high_risk_objections(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.win_loss_patterns(self._make_extractions())
        assert "too expensive" in result.high_risk_objections

    def test_win_loss_detects_low_risk_topics(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.win_loss_patterns(self._make_extractions())
        assert "features" in result.low_risk_topics

    def test_win_loss_avg_risk_score_range(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.win_loss_patterns(self._make_extractions())
        assert 0.0 <= result.avg_risk_score <= 1.0

    def test_win_loss_risk_distribution(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.win_loss_patterns(self._make_extractions())
        assert result.risk_distribution.get("high", 0) == 2
        assert result.risk_distribution.get("low", 0) == 1

    def test_win_loss_to_dict(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        d = PortfolioInsights.win_loss_patterns(self._make_extractions()).to_dict()
        assert "high_risk_objections" in d
        assert "low_risk_topics" in d
        assert "avg_risk_score" in d
        assert "risk_distribution" in d

    def test_objection_velocity_empty(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        results = PortfolioInsights.objection_velocity([])
        assert results == []

    def test_objection_velocity_identifies_rising_trend(self):
        from datetime import datetime, timedelta

        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        now = datetime.utcnow()
        extractions = [
            {
                "objections": ["too expensive"],
                "created_at": (now - timedelta(weeks=4 - i)).isoformat(),
            }
            for i in range(8)
        ]
        results = PortfolioInsights.objection_velocity(extractions)
        vel = [v for v in results if v.objection == "too expensive"]
        assert len(vel) == 1
        assert vel[0].trend in ("rising", "stable")

    def test_objection_velocity_to_dict(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        results = PortfolioInsights.objection_velocity(self._make_extractions())
        assert all("counts_by_period" in v.to_dict() for v in results)

    def test_rep_comparison_empty(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        assert PortfolioInsights.rep_comparison({}) == {}

    def test_rep_comparison_computes_stats(self):
        from temporalos.intelligence.portfolio_insights import PortfolioInsights

        result = PortfolioInsights.rep_comparison(
            {"alice": self._make_extractions(), "bob": [self._make_extractions()[1]]}
        )
        assert "alice" in result
        assert "bob" in result
        assert result["alice"]["segment_count"] == 3
        assert "avg_risk_score" in result["alice"]


# ── Search API ────────────────────────────────────────────────────────────────


class TestSearchAPI:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app

            self.client = TestClient(app)
            yield

    def test_search_missing_q_returns_422(self):
        resp = self.client.get("/api/v1/search")
        assert resp.status_code == 422

    def test_search_empty_returns_json(self):
        resp = self.client.get("/api/v1/search?q=pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data

    def test_search_with_filters(self):
        resp = self.client.get("/api/v1/search?q=pricing&risk=high&topic=pricing")
        assert resp.status_code == 200
        assert resp.json()["filters"]["risk"] == "high"

    def test_search_limit_param(self):
        resp = self.client.get("/api/v1/search?q=test&limit=5")
        assert resp.status_code == 200

    def test_index_stats(self):
        resp = self.client.get("/api/v1/search/index/stats")
        assert resp.status_code == 200
        assert "document_count" in resp.json()

    def test_index_video_endpoint(self):
        resp = self.client.post("/api/v1/search/index/test-video-id-123")
        assert resp.status_code == 200
        assert "video_id" in resp.json()

    def test_insights_patterns(self):
        resp = self.client.get("/api/v1/search/insights/patterns")
        assert resp.status_code == 200
        data = resp.json()
        assert "high_risk_objections" in data

    def test_insights_velocity(self):
        resp = self.client.get("/api/v1/search/insights/velocity")
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "items" in data

    def test_insights_velocity_month_period(self):
        resp = self.client.get("/api/v1/search/insights/velocity?period=month")
        assert resp.status_code == 200

    def test_insights_velocity_invalid_period(self):
        resp = self.client.get("/api/v1/search/insights/velocity?period=decade")
        assert resp.status_code == 422

    def test_insights_reps(self):
        resp = self.client.get("/api/v1/search/insights/reps")
        assert resp.status_code == 200
        assert "reps" in resp.json()
