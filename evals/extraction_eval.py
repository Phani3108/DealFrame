"""
TemporalOS Extraction Evaluation Suite — Phase 4.

Uses DeepEval to run structured quality checks on extraction outputs.
Tracks per-field accuracy and can run regression testing to catch model drift.

Run with:
  python -m pytest evals/ -v

Or directly:
  python evals/extraction_eval.py
"""

from __future__ import annotations

import json
from typing import Any


# ── DeepEval custom metrics ────────────────────────────────────────────────────

try:
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase

    class TopicAccuracyMetric(BaseMetric):
        """Checks that extracted topic is a valid taxonomy value."""

        VALID_TOPICS = {
            "pricing", "features", "competition", "timeline",
            "security", "onboarding", "support", "legal", "other",
        }

        def __init__(self, threshold: float = 1.0) -> None:
            self.threshold = threshold

        @property
        def name(self) -> str:
            return "TopicAccuracy"

        def measure(self, test_case: LLMTestCase) -> float:
            output = _safe_json(test_case.actual_output)
            topic = output.get("topic", "")
            self.score = 1.0 if topic in self.VALID_TOPICS else 0.0
            self.success = self.score >= self.threshold
            return self.score

        async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return self.success

    class RiskScoreRangeMetric(BaseMetric):
        """Checks that risk_score is within [0, 1] and matches risk label direction."""

        def __init__(self, threshold: float = 1.0) -> None:
            self.threshold = threshold

        @property
        def name(self) -> str:
            return "RiskScoreRange"

        def measure(self, test_case: LLMTestCase) -> float:
            output = _safe_json(test_case.actual_output)
            score = float(output.get("risk_score", -1))
            risk = output.get("risk", "")

            in_range = 0.0 <= score <= 1.0
            direction_ok = True
            if risk == "high" and score < 0.5:
                direction_ok = False
            if risk == "low" and score > 0.5:
                direction_ok = False

            self.score = 1.0 if (in_range and direction_ok) else 0.0
            self.success = self.score >= self.threshold
            return self.score

        async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return self.success

    class ObjectionListMetric(BaseMetric):
        """Checks that objections field is a non-null list."""

        def __init__(self, threshold: float = 1.0) -> None:
            self.threshold = threshold

        @property
        def name(self) -> str:
            return "ObjectionList"

        def measure(self, test_case: LLMTestCase) -> float:
            output = _safe_json(test_case.actual_output)
            objections = output.get("objections")
            self.score = 1.0 if isinstance(objections, list) else 0.0
            self.success = self.score >= self.threshold
            return self.score

        async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return self.success

    class ConfidenceRangeMetric(BaseMetric):
        """Checks that confidence is within [0, 1]."""

        def __init__(self, threshold: float = 1.0) -> None:
            self.threshold = threshold

        @property
        def name(self) -> str:
            return "ConfidenceRange"

        def measure(self, test_case: LLMTestCase) -> float:
            output = _safe_json(test_case.actual_output)
            conf = output.get("confidence", -1)
            self.score = 1.0 if 0.0 <= float(conf) <= 1.0 else 0.0
            self.success = self.score >= self.threshold
            return self.score

        async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return self.success

    _DEEPEVAL_AVAILABLE = True

except ImportError:
    _DEEPEVAL_AVAILABLE = False
    TopicAccuracyMetric = None  # type: ignore[assignment, misc]
    RiskScoreRangeMetric = None  # type: ignore[assignment, misc]
    ObjectionListMetric = None  # type: ignore[assignment, misc]
    ConfidenceRangeMetric = None  # type: ignore[assignment, misc]


# ── Standalone evaluation (no DeepEval required) ──────────────────────────────

def evaluate_extraction_output(output: dict | str) -> dict[str, bool]:
    """
    Quick schema validation of an extraction payload.
    Returns {check_name: passed} for each check.
    """
    payload = _safe_json(output) if isinstance(output, str) else output

    VALID_TOPICS = {
        "pricing", "features", "competition", "timeline",
        "security", "onboarding", "support", "legal", "other",
    }
    VALID_SENTIMENTS = {"positive", "neutral", "negative", "hesitant"}
    VALID_RISKS = {"low", "medium", "high"}

    checks: dict[str, bool] = {
        "has_topic": "topic" in payload,
        "valid_topic": payload.get("topic", "") in VALID_TOPICS,
        "has_sentiment": "sentiment" in payload,
        "valid_sentiment": payload.get("sentiment", "") in VALID_SENTIMENTS,
        "has_risk": "risk" in payload,
        "valid_risk": payload.get("risk", "") in VALID_RISKS,
        "has_risk_score": "risk_score" in payload,
        "risk_score_in_range": 0.0 <= float(payload.get("risk_score", -1)) <= 1.0,
        "risk_direction_consistent": _risk_direction_ok(
            payload.get("risk", ""), payload.get("risk_score", 0.5)
        ),
        "objections_is_list": isinstance(payload.get("objections"), list),
        "decision_signals_is_list": isinstance(payload.get("decision_signals"), list),
        "has_confidence": "confidence" in payload,
        "confidence_in_range": 0.0 <= float(payload.get("confidence", -1)) <= 1.0,
    }
    return checks


def schema_pass_rate(outputs: list[dict | str]) -> float:
    """Return the fraction of outputs that pass all schema checks."""
    if not outputs:
        return 1.0
    passed = sum(
        1 for o in outputs if all(evaluate_extraction_output(o).values())
    )
    return passed / len(outputs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_json(text: str | dict) -> dict:
    if isinstance(text, dict):
        return text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _risk_direction_ok(risk: str, risk_score: Any) -> bool:
    try:
        score = float(risk_score)
    except (TypeError, ValueError):
        return False
    if risk == "high" and score < 0.5:
        return False
    if risk == "low" and score > 0.5:
        return False
    return True
