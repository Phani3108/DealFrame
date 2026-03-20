"""Unit tests — extraction base + GPT-4o adapter (API mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from temporalos.core.types import AlignedSegment, ExtractionResult, Frame, Word
from temporalos.extraction.base import BaseExtractionModel
from temporalos.extraction.models.gpt4o import GPT4oExtractionModel


# ── BaseExtractionModel contract tests ────────────────────────────────────────


class _ConcreteExtractor(BaseExtractionModel):
    name = "test"

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        return ExtractionResult(
            topic="test",
            sentiment="positive",
            risk="low",
            risk_score=0.1,
            model_name=self.name,
        )


def test_base_model_abstract():
    """Cannot instantiate the abstract base directly."""
    with pytest.raises(TypeError):
        BaseExtractionModel()  # type: ignore[abstract]


def test_concrete_model_extract_batch(sample_segments):
    model = _ConcreteExtractor()
    results = model.extract_batch(sample_segments[:3])
    assert len(results) == 3
    assert all(isinstance(r, ExtractionResult) for r in results)


# ── GPT-4o adapter tests (OpenAI calls mocked) ────────────────────────────────


def _make_openai_response(payload: dict) -> MagicMock:
    """Build a minimal mock matching openai.ChatCompletion structure."""
    choice = MagicMock()
    choice.message.content = json.dumps(payload)
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture()
def gpt4o_model():
    return GPT4oExtractionModel(model="gpt-4o", api_key="sk-test")


@pytest.fixture()
def segment_with_frame(sample_frames, sample_words):
    return AlignedSegment(
        timestamp_ms=0,
        frame=sample_frames[0],
        words=sample_words[:5],
    )


@pytest.fixture()
def segment_no_frame(sample_words):
    return AlignedSegment(timestamp_ms=2000, frame=None, words=sample_words[5:10])


def test_gpt4o_extract_returns_extraction_result(gpt4o_model, segment_with_frame):
    mock_payload = {
        "topic": "pricing",
        "sentiment": "hesitant",
        "risk": "high",
        "risk_score": 0.75,
        "objections": ["Pricing seems high"],
        "decision_signals": [],
        "confidence": 0.85,
    }
    with patch.object(
        gpt4o_model._client.chat.completions,
        "create",
        return_value=_make_openai_response(mock_payload),
    ):
        result = gpt4o_model.extract(segment_with_frame)

    assert isinstance(result, ExtractionResult)
    assert result.topic == "pricing"
    assert result.sentiment == "hesitant"
    assert result.risk == "high"
    assert result.risk_score == pytest.approx(0.75)
    assert result.objections == ["Pricing seems high"]
    assert result.model_name == "gpt4o"
    assert result.latency_ms >= 0


def test_gpt4o_extract_no_frame(gpt4o_model, segment_no_frame):
    """Extraction should work even when there's no frame (audio-only segment)."""
    mock_payload = {
        "topic": "features",
        "sentiment": "positive",
        "risk": "low",
        "risk_score": 0.2,
        "objections": [],
        "decision_signals": ["Interested in enterprise plan"],
        "confidence": 0.9,
    }
    with patch.object(
        gpt4o_model._client.chat.completions,
        "create",
        return_value=_make_openai_response(mock_payload),
    ):
        result = gpt4o_model.extract(segment_no_frame)

    assert result.topic == "features"
    assert result.decision_signals == ["Interested in enterprise plan"]


def test_gpt4o_extract_partial_response(gpt4o_model, segment_no_frame):
    """Missing keys in the API response should get safe defaults."""
    mock_payload = {"topic": "pricing"}  # intentionally incomplete
    with patch.object(
        gpt4o_model._client.chat.completions,
        "create",
        return_value=_make_openai_response(mock_payload),
    ):
        result = gpt4o_model.extract(segment_no_frame)

    assert result.topic == "pricing"
    assert result.sentiment == "neutral"   # default
    assert result.risk == "low"            # default
    assert result.objections == []
