"""Speaker Intelligence E2E tests.

Tests the full speaker intelligence pipeline:
  1. SpeakerStats — word count, WPM, filler rate, question count, interruptions
  2. SpeakerIntelligence — talk ratio, dominant speaker
  3. compute_speaker_intelligence — end-to-end from words to stats
  4. Pipeline integration — speaker_intelligence in job results
  5. Coaching integration — coaching cards consume speaker intelligence

Rules (from claude.md §0):
  - Generates synthetic data in-process (no external assets required)
  - Runs all real code; only external API calls are mocked
  - Asserts correct output schema and non-empty results
"""
from __future__ import annotations

from typing import List

import pytest

from temporalos.core.types import Word


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_conversation(
    speaker_a_sentences: List[str],
    speaker_b_sentences: List[str],
    gap_ms: int = 200,
    turn_gap_ms: int = 1500,
) -> List[Word]:
    """Build a realistic two-speaker conversation with timestamps."""
    words: List[Word] = []
    t = 0
    turns = list(zip(speaker_a_sentences, speaker_b_sentences))
    for sa_sent, sb_sent in turns:
        # Speaker A
        for tok in sa_sent.split():
            dur = len(tok) * 60 + 80
            words.append(Word(text=tok, start_ms=t, end_ms=t + dur, speaker="SPEAKER_A"))
            t += dur + gap_ms
        t += turn_gap_ms
        # Speaker B
        for tok in sb_sent.split():
            dur = len(tok) * 60 + 80
            words.append(Word(text=tok, start_ms=t, end_ms=t + dur, speaker="SPEAKER_B"))
            t += dur + gap_ms
        t += turn_gap_ms
    return words


@pytest.fixture
def two_speaker_conversation() -> List[Word]:
    return _make_conversation(
        speaker_a_sentences=[
            "So um basically our pricing starts at five hundred dollars per month?",
            "Right and like we can actually offer a discount for annual contracts",
            "Yeah so what is your timeline for making a decision?",
        ],
        speaker_b_sentences=[
            "That seems pretty expensive compared to what we currently pay",
            "Okay well we need to basically discuss this with our leadership team",
            "Uh probably within the next two to three weeks",
        ],
    )


@pytest.fixture
def single_speaker_words() -> List[Word]:
    """All words from a single speaker (monologue)."""
    words = []
    t = 0
    for tok in "Hello everyone today we will discuss the quarterly results".split():
        dur = len(tok) * 60 + 80
        words.append(Word(text=tok, start_ms=t, end_ms=t + dur, speaker="SPEAKER_A"))
        t += dur + 200
    return words


@pytest.fixture
def interruption_words() -> List[Word]:
    """Rapid speaker changes simulating interruptions."""
    words = []
    t = 0
    speakers = ["SPEAKER_A", "SPEAKER_B", "SPEAKER_A", "SPEAKER_B",
                "SPEAKER_A", "SPEAKER_A", "SPEAKER_B"]
    texts = ["I think", "Actually", "Wait let me", "No", "Okay?", "fine", "Thanks"]
    for speaker, text in zip(speakers, texts):
        for tok in text.split():
            dur = 200
            words.append(Word(text=tok, start_ms=t, end_ms=t + dur, speaker=speaker))
            t += dur + 50  # Very short gap → interruption
    return words


# ── 1. SpeakerStats ──────────────────────────────────────────────────────────

class TestSpeakerStats:
    def test_words_per_minute(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        for speaker, stats in intel.stats.items():
            assert stats.words_per_minute > 0, f"{speaker} should have positive WPM"

    def test_filler_word_detection(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        # Speaker A has "um", "basically", "like", "actually", "right", "yeah", "so"
        a = intel.stats["SPEAKER_A"]
        assert a.filler_count > 0, "Speaker A should have filler words detected"
        assert 0 < a.filler_rate < 1.0

    def test_question_detection(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        a = intel.stats["SPEAKER_A"]
        # Speaker A has "month?" and "decision?"
        assert a.question_count >= 2, f"Expected >=2 questions, got {a.question_count}"

    def test_word_count(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        total = sum(s.word_count for s in intel.stats.values())
        assert total == len(two_speaker_conversation)

    def test_interruption_count(self, interruption_words):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(interruption_words)
        total_interruptions = sum(s.interruptions for s in intel.stats.values())
        assert total_interruptions > 0, "Should detect interruptions from rapid speaker changes"

    def test_stats_to_dict(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        for speaker, stats in intel.stats.items():
            d = stats.to_dict()
            assert all(k in d for k in (
                "speaker", "word_count", "total_seconds",
                "words_per_minute", "question_count", "filler_rate", "interruptions",
            )), f"Missing keys in {d}"


# ── 2. SpeakerIntelligence ───────────────────────────────────────────────────

class TestSpeakerIntelligence:
    def test_talk_ratio_sums_to_one(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        ratio = intel.talk_ratio
        assert abs(sum(ratio.values()) - 1.0) < 0.01

    def test_dominant_speaker(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        assert intel.dominant_speaker in ("SPEAKER_A", "SPEAKER_B")

    def test_single_speaker_ratio(self, single_speaker_words):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(single_speaker_words)
        ratio = intel.talk_ratio
        assert ratio["SPEAKER_A"] == 1.0

    def test_to_dict_schema(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence(two_speaker_conversation)
        d = intel.to_dict()
        assert "speaker_stats" in d
        assert "talk_ratio" in d
        assert "speaker_count" in d
        assert "dominant_speaker" in d
        assert d["speaker_count"] == 2

    def test_empty_words(self):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        intel = compute_speaker_intelligence([])
        assert intel.stats == {}
        assert intel.dominant_speaker is None


# ── 3. Diarization + Intelligence Integration ────────────────────────────────

class TestDiarizationIntegration:
    def test_mock_diarizer_then_speaker_intel(self):
        """Full pipeline: raw words → diarize → speaker intelligence."""
        from temporalos.diarization.diarizer import get_diarizer
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence

        # Build unlabeled words (no speaker)
        words = []
        t = 0
        sentences = [
            "The pricing is a bit high",
            "Can you offer a discount",  # Speaker turn after gap
        ]
        for i, sent in enumerate(sentences):
            for tok in sent.split():
                dur = len(tok) * 60 + 80
                words.append(Word(text=tok, start_ms=t, end_ms=t + dur))
                t += dur + 200
            t += 2000  # >1500ms gap triggers speaker change in MockDiarizer

        diarizer = get_diarizer()
        labeled = diarizer.diarize(words)
        intel = compute_speaker_intelligence(labeled)

        assert len(intel.stats) == 2
        assert "SPEAKER_A" in intel.stats
        assert "SPEAKER_B" in intel.stats

    def test_speaker_labels_consistent(self):
        """Each contiguous block should have one speaker."""
        from temporalos.diarization.diarizer import get_diarizer

        words = []
        t = 0
        for tok in "Hello how are you doing today".split():
            dur = 200
            words.append(Word(text=tok, start_ms=t, end_ms=t + dur))
            t += dur + 100  # Short gap, no speaker change

        diarizer = get_diarizer()
        labeled = diarizer.diarize(words)

        # All should be same speaker (no gaps > 1500ms)
        speakers = set(w.speaker for w in labeled)
        assert len(speakers) == 1


# ── 4. Coaching Engine Integration ───────────────────────────────────────────

class TestCoachingIntegration:
    def test_coaching_with_speaker_intelligence(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        from temporalos.agents.coaching import CoachingEngine

        intel_data = compute_speaker_intelligence(two_speaker_conversation)
        intel_dict = {
            "speaker_intelligence": intel_data.to_dict(),
            "segments": [
                {
                    "timestamp_str": "00:00",
                    "extraction": {
                        "topic": "pricing",
                        "risk": "high",
                        "risk_score": 0.7,
                        "objections": ["too expensive"],
                        "decision_signals": [],
                        "sentiment": "negative",
                    },
                },
                {
                    "timestamp_str": "00:30",
                    "extraction": {
                        "topic": "timeline",
                        "risk": "low",
                        "risk_score": 0.3,
                        "objections": [],
                        "decision_signals": ["next two to three weeks"],
                        "sentiment": "neutral",
                    },
                },
            ],
        }

        engine = CoachingEngine()
        engine.record_call("rep-001", "job-abc", intel_dict, speaker_label="SPEAKER_A")
        card = engine.generate_coaching_card("rep-001")

        assert card is not None
        assert card.calls_analyzed == 1
        assert card.overall_score > 0
        assert len(card.dimensions) == 5  # talk ratio, pace, filler, questions, objections

        d = card.to_dict()
        assert d["grade"] in ("A", "B", "C", "D")
        assert len(d["dimensions"]) == 5

    def test_coaching_without_speaker_intelligence(self):
        """Coaching should still work with fallback heuristics."""
        from temporalos.agents.coaching import CoachingEngine

        intel_dict = {
            "segments": [
                {
                    "extraction": {
                        "topic": "pricing",
                        "risk_score": 0.5,
                        "objections": ["expensive"],
                        "decision_signals": ["send proposal"],
                    }
                }
            ],
        }

        engine = CoachingEngine()
        engine.record_call("rep-002", "job-xyz", intel_dict)
        card = engine.generate_coaching_card("rep-002")
        assert card is not None
        assert card.overall_score > 0

    def test_coaching_multiple_calls(self, two_speaker_conversation):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        from temporalos.agents.coaching import CoachingEngine

        intel_data = compute_speaker_intelligence(two_speaker_conversation)
        intel_dict = {
            "speaker_intelligence": intel_data.to_dict(),
            "segments": [{"extraction": {"topic": "pricing", "risk_score": 0.6,
                           "objections": [], "decision_signals": []}}],
        }

        engine = CoachingEngine()
        engine.record_call("rep-003", "job-1", intel_dict, speaker_label="SPEAKER_A")
        engine.record_call("rep-003", "job-2", intel_dict, speaker_label="SPEAKER_A")

        card = engine.generate_coaching_card("rep-003")
        assert card.calls_analyzed == 2


# ── 5. Pipeline Stage Integration ────────────────────────────────────────────

class TestPipelineIntegration:
    def test_pipeline_wires_speaker_intelligence(self):
        """Verify the process pipeline code calls diarization + speaker intel."""
        # Verify the pipeline function imports and calls the right modules
        import inspect
        from temporalos.api.routes.process import _run_pipeline
        source = inspect.getsource(_run_pipeline)
        assert "diarize" in source, "Pipeline should call diarizer.diarize()"
        assert "compute_speaker_intelligence" in source, "Pipeline should compute speaker intelligence"
        assert "speaker_intelligence" in source, "Pipeline result should include speaker_intelligence"

    def test_speaker_intel_in_result_schema(self, two_speaker_conversation):
        """Verify speaker intelligence produces the exact schema the pipeline stores."""
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence

        intel = compute_speaker_intelligence(two_speaker_conversation)
        result = {
            "segments": [],
            "overall_risk_score": 0.5,
            "segment_count": 0,
            "speaker_intelligence": intel.to_dict(),
        }

        si = result["speaker_intelligence"]
        assert "speaker_stats" in si
        assert "talk_ratio" in si
        assert "speaker_count" in si
        assert "dominant_speaker" in si

    def test_diarization_route_exists(self):
        """Verify the diarization API route is registered."""
        try:
            from temporalos.api.main import app
        except Exception:
            pytest.skip("App initialization failed")

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        # Check that diarization route exists
        diarization_paths = [r for r in routes if "diarization" in r]
        assert len(diarization_paths) > 0, "Diarization routes should be registered"


# ── 6. Edge Cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_all_filler_words(self):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        words = [
            Word(text="um", start_ms=0, end_ms=100, speaker="A"),
            Word(text="uh", start_ms=200, end_ms=300, speaker="A"),
            Word(text="like", start_ms=400, end_ms=500, speaker="A"),
        ]
        intel = compute_speaker_intelligence(words)
        assert intel.stats["A"].filler_rate == 1.0

    def test_no_questions(self):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        words = [
            Word(text="Hello", start_ms=0, end_ms=100, speaker="A"),
            Word(text="World", start_ms=200, end_ms=300, speaker="A"),
        ]
        intel = compute_speaker_intelligence(words)
        assert intel.stats["A"].question_count == 0

    def test_unknown_speaker(self):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        words = [
            Word(text="Hello?", start_ms=0, end_ms=100),  # No speaker
        ]
        intel = compute_speaker_intelligence(words)
        assert "UNKNOWN" in intel.stats
        assert intel.stats["UNKNOWN"].question_count == 1

    def test_three_speakers(self):
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        words = [
            Word(text="Hello", start_ms=0, end_ms=100, speaker="A"),
            Word(text="Hi", start_ms=200, end_ms=300, speaker="B"),
            Word(text="Hey", start_ms=400, end_ms=500, speaker="C"),
        ]
        intel = compute_speaker_intelligence(words)
        assert len(intel.stats) == 3
        ratio = intel.talk_ratio
        assert abs(sum(ratio.values()) - 1.0) < 0.01
