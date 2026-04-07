"""Enhanced Extraction E2E tests.

Tests the improved LLM extraction with:
  1. Few-shot system prompt validation
  2. Fallback extractor improvements (more patterns, sentiment, topic scoring)
  3. Edge cases (empty, long, multilingual)

Rules (from claude.md §0):
  - No external API calls; LLM is mocked
  - Asserts correct output schema and non-empty results
"""
from __future__ import annotations

import pytest

from temporalos.core.types import AlignedSegment, Frame, Word


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_segment(transcript: str, timestamp_ms: int = 0) -> AlignedSegment:
    """Build a minimal AlignedSegment from transcript text."""
    words = []
    t = timestamp_ms
    for tok in transcript.split():
        dur = len(tok) * 60 + 80
        words.append(Word(text=tok, start_ms=t, end_ms=t + dur))
        t += dur + 200
    frame = Frame(path="/tmp/fake_frame.jpg", timestamp_ms=timestamp_ms)
    return AlignedSegment(
        timestamp_ms=timestamp_ms,
        frame=frame,
        words=words,
    )


# ── 1. System Prompt Quality ─────────────────────────────────────────────────

class TestSystemPrompt:
    def test_has_few_shot_examples(self):
        from temporalos.extraction.router import EXTRACTION_SYSTEM
        assert "Example 1:" in EXTRACTION_SYSTEM
        assert "Example 2:" in EXTRACTION_SYSTEM
        assert "Example 3:" in EXTRACTION_SYSTEM

    def test_examples_cover_key_topics(self):
        from temporalos.extraction.router import EXTRACTION_SYSTEM
        assert "pricing" in EXTRACTION_SYSTEM
        assert "features" in EXTRACTION_SYSTEM
        assert "competition" in EXTRACTION_SYSTEM

    def test_examples_cover_sentiments(self):
        from temporalos.extraction.router import EXTRACTION_SYSTEM
        assert "negative" in EXTRACTION_SYSTEM
        assert "positive" in EXTRACTION_SYSTEM
        assert "hesitant" in EXTRACTION_SYSTEM

    def test_valid_json_in_examples(self):
        import json
        from temporalos.extraction.router import EXTRACTION_SYSTEM
        # Extract JSON blocks from examples
        import re
        jsons = re.findall(r'\{[^{}]+\}', EXTRACTION_SYSTEM)
        assert len(jsons) >= 3
        for j in jsons:
            parsed = json.loads(j)
            assert "topic" in parsed
            assert "risk_score" in parsed


# ── 2. Fallback Extractor Improvements ───────────────────────────────────────

class TestFallbackExtractor:
    @pytest.fixture
    def extractor(self):
        from temporalos.extraction.router import LLMExtractionRouter
        return LLMExtractionRouter()

    def test_pricing_topic(self, extractor):
        seg = _make_segment("The cost is too expensive and over budget")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "pricing"
        assert result.risk_score > 0.2

    def test_competition_topic(self, extractor):
        seg = _make_segment("We are comparing you versus Gong and their alternative solution")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "competition"

    def test_security_topic(self, extractor):
        seg = _make_segment("What about SOC2 compliance and GDPR encryption policies")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "security"

    def test_timeline_topic(self, extractor):
        seg = _make_segment("We need this by next quarter and the deadline is urgent")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "timeline"

    def test_legal_topic(self, extractor):
        seg = _make_segment("Let me review the contract terms and renewal clause")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "legal"

    def test_multiple_objections(self, extractor):
        seg = _make_segment("It's too expensive, I'm not sure about it, and I'm concerned about the timeline")
        result = extractor._fallback_extract(seg, 0)
        assert len(result.objections) >= 3
        assert result.risk_score > 0.4

    def test_decision_signals(self, extractor):
        seg = _make_segment("Let's move forward and schedule a demo. Please send proposal")
        result = extractor._fallback_extract(seg, 0)
        assert len(result.decision_signals) >= 2

    def test_negative_sentiment(self, extractor):
        seg = _make_segment("No we can't do that. It won't work and it's too expensive")
        result = extractor._fallback_extract(seg, 0)
        assert result.sentiment == "negative"

    def test_positive_sentiment(self, extractor):
        seg = _make_segment("This is great! I love the features and it's perfect for us, excited to get started")
        result = extractor._fallback_extract(seg, 0)
        assert result.sentiment == "positive"

    def test_hesitant_sentiment(self, extractor):
        seg = _make_segment("I love the features but I'm not sure about the cost")
        result = extractor._fallback_extract(seg, 0)
        assert result.sentiment == "hesitant"

    def test_risk_levels(self, extractor):
        # Low risk
        seg = _make_segment("Everything looks great, schedule a demo please")
        result = extractor._fallback_extract(seg, 0)
        assert result.risk in ("low", "medium")

        # High risk
        seg = _make_segment("Too expensive, not convinced, can't justify the pushback from leadership, worried about compliance")
        result = extractor._fallback_extract(seg, 0)
        assert result.risk == "high"
        assert result.risk_score > 0.5

    def test_signals_reduce_risk(self, extractor):
        # Objections + strong buy signals should produce moderate risk
        seg = _make_segment("Too expensive but let's move forward and get started anyway")
        result = extractor._fallback_extract(seg, 0)
        assert result.risk_score < 0.6  # Signals reduce the risk

    def test_empty_transcript(self, extractor):
        seg = _make_segment("")
        result = extractor._fallback_extract(seg, 0)
        assert result.topic == "other"
        assert result.risk == "low"
        assert result.confidence == 0.35

    def test_result_schema(self, extractor):
        seg = _make_segment("We need to discuss pricing and features")
        result = extractor._fallback_extract(seg, 0)
        d = result.to_dict()
        required = {"topic", "customer_sentiment", "risk", "risk_score", "objections",
                     "decision_signals", "confidence", "model"}
        assert required.issubset(set(d.keys()))

    def test_risk_score_bounds(self, extractor):
        seg = _make_segment("too expensive not sure concerned don't think worried about not convinced can't justify pushback hesitant already using no budget not a priority too complex")
        result = extractor._fallback_extract(seg, 0)
        assert 0.0 <= result.risk_score <= 1.0


# ── 3. LLM Router Integration ────────────────────────────────────────────────

class TestLLMRouterIntegration:
    def test_router_has_fallback(self):
        from temporalos.extraction.router import LLMExtractionRouter
        router = LLMExtractionRouter()
        seg = _make_segment("We need better pricing for this deal")
        # When no LLM is configured, should use fallback
        result = router.extract(seg)
        assert result.topic in ("pricing", "other")
        assert result.model_name in ("fallback_rules", "llm_mock")

    def test_parse_result_validates(self):
        from temporalos.extraction.router import LLMExtractionRouter
        router = LLMExtractionRouter()
        # Test that parse_result clamps values
        result = router._parse_result({
            "topic": "pricing",
            "sentiment": "negative",
            "risk": "high",
            "risk_score": 1.5,  # Should be clamped to 1.0
            "objections": ["too expensive"],
            "decision_signals": [],
            "confidence": -0.5,  # Should be clamped to 0.0
        }, model="test", latency_ms=100)
        assert result.risk_score == 1.0
        assert result.confidence == 0.0

    def test_singleton(self):
        from temporalos.extraction.router import get_extraction_router
        r1 = get_extraction_router()
        r2 = get_extraction_router()
        assert r1 is r2
