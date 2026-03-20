"""Unit tests — core types."""

from temporalos.core.types import (
    AlignedSegment,
    ExtractionResult,
    Frame,
    VideoIntelligence,
    Word,
)


def test_frame_timestamp_str():
    f = Frame(path="/tmp/frame.jpg", timestamp_ms=92000)
    assert f.timestamp_str == "01:32"


def test_word_basic():
    w = Word(text="hello", start_ms=500, end_ms=900)
    assert w.text == "hello"


def test_aligned_segment_transcript(sample_words):
    seg = AlignedSegment(
        timestamp_ms=0,
        frame=Frame(path="/tmp/f.jpg", timestamp_ms=0),
        words=sample_words[:5],
    )
    assert "pricing" in seg.transcript


def test_aligned_segment_duration(sample_words):
    seg = AlignedSegment(timestamp_ms=0, frame=None, words=sample_words[:5])
    assert seg.duration_ms == sample_words[4].end_ms - sample_words[0].start_ms


def test_extraction_result_to_dict():
    ext = ExtractionResult(
        topic="pricing",
        sentiment="hesitant",
        risk="high",
        risk_score=0.8,
        objections=["Too expensive"],
        decision_signals=["Send proposal"],
        confidence=0.9,
        model_name="gpt4o",
    )
    d = ext.to_dict()
    assert d["topic"] == "pricing"
    assert d["customer_sentiment"] == "hesitant"
    assert d["risk_score"] == 0.8
    assert "Too expensive" in d["objections"]


def test_video_intelligence_overall_risk():
    from temporalos.core.types import AlignedSegment

    seg = AlignedSegment(timestamp_ms=0, frame=None, words=[])
    ext1 = ExtractionResult("pricing", "positive", "low", 0.2, model_name="gpt4o")
    ext2 = ExtractionResult("features", "hesitant", "high", 0.8, model_name="gpt4o")
    vi = VideoIntelligence(
        video_path="test.mp4",
        duration_ms=10000,
        segments=[(seg, ext1), (seg, ext2)],
    )
    assert vi.overall_risk_score == pytest.approx(0.5)
    d = vi.to_dict()
    assert len(d["segments"]) == 2
    assert d["overall_risk_score"] == 0.5


import pytest  # noqa: E402  (placed after fixtures to keep assertions clean)
