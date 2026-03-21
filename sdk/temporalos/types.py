"""TemporalOS SDK type stubs — thin dataclasses for IDE completion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Job:
    job_id: str
    status: str
    video_url: str = ""
    created_at: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Job":
        return cls(
            job_id=d.get("job_id", ""),
            status=d.get("status", ""),
            video_url=d.get("video_url", ""),
            created_at=d.get("created_at", 0.0),
        )


@dataclass
class ExtractionResult:
    topic: str = ""
    risk: str = "low"
    risk_score: float = 0.0
    sentiment: str = "neutral"
    objections: List[str] = field(default_factory=list)
    decision_signals: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExtractionResult":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})  # type: ignore[attr-defined]


@dataclass
class Segment:
    timestamp_str: str = ""
    timestamp_ms: int = 0
    transcript: str = ""
    extraction: ExtractionResult = field(default_factory=ExtractionResult)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Segment":
        return cls(
            timestamp_str=d.get("timestamp_str", ""),
            timestamp_ms=d.get("timestamp_ms", 0),
            transcript=d.get("transcript", ""),
            extraction=ExtractionResult.from_dict(d.get("extraction", {})),
        )


@dataclass
class Intelligence:
    job_id: str = ""
    overall_risk_score: float = 0.0
    segments: List[Segment] = field(default_factory=list)
    duration_ms: int = 0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Intelligence":
        raw = d.get("intelligence", d)
        return cls(
            job_id=d.get("job_id", ""),
            overall_risk_score=raw.get("overall_risk_score", 0.0),
            segments=[Segment.from_dict(s) for s in raw.get("segments", [])],
            duration_ms=raw.get("duration_ms", 0),
        )


@dataclass
class SearchResult:
    job_id: str = ""
    timestamp_str: str = ""
    score: float = 0.0
    snippet: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SearchResult":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})  # type: ignore[attr-defined]


@dataclass
class QAAnswer:
    question: str = ""
    answer: str = ""
    citations: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QAAnswer":
        return cls(question=d.get("question", ""), answer=d.get("answer", ""),
                   citations=d.get("citations", []))


@dataclass
class RiskAlert:
    job_id: str = ""
    alert_type: str = ""
    risk_score: float = 0.0
    company: str = ""
    message: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RiskAlert":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})  # type: ignore[attr-defined]


@dataclass
class CoachingCard:
    rep_id: str = ""
    overall_score: float = 0.0
    grade: str = ""
    calls_analyzed: int = 0
    strengths: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CoachingCard":
        return cls(rep_id=d.get("rep_id", ""), overall_score=d.get("overall_score", 0.0),
                   grade=d.get("grade", ""), calls_analyzed=d.get("calls_analyzed", 0),
                   strengths=d.get("strengths", []), improvements=d.get("improvements", []))


@dataclass
class MeetingBrief:
    company: str = ""
    prior_calls: int = 0
    risk_trajectory: str = "new"
    talking_points: List[str] = field(default_factory=list)
    watch_outs: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MeetingBrief":
        return cls(company=d.get("company", ""), prior_calls=d.get("prior_calls", 0),
                   risk_trajectory=d.get("risk_trajectory", "new"),
                   talking_points=d.get("talking_points", []), watch_outs=d.get("watch_outs", []))


@dataclass
class BatchJob:
    batch_id: str = ""
    status: str = ""
    total: int = 0
    completed: int = 0
    failed: int = 0
    progress_pct: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BatchJob":
        return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()})  # type: ignore[attr-defined]


@dataclass
class Webhook:
    id: str = ""
    url: str = ""
    events: List[str] = field(default_factory=list)
    active: bool = True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Webhook":
        return cls(id=d.get("id", ""), url=d.get("url", ""),
                   events=d.get("events", []), active=d.get("active", True))


@dataclass
class Schema:
    id: str = ""
    name: str = ""
    vertical: str = ""
    field_count: int = 0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Schema":
        return cls(id=d.get("id", ""), name=d.get("name", ""),
                   vertical=d.get("vertical", ""),
                   field_count=len(d.get("fields", [])))
