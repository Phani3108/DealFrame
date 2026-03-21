"""Temporal Diff Engine — semantic comparison of two calls.

Compares two calls with the same company and generates:
- New objections / resolved objections
- Topic evolution (new / dropped topics)
- Risk trajectory (delta + direction)
- Sentiment shift
- Decision signal changes
Unique competitive moat — nobody has call-to-call semantic diff.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class DiffResult:
    """Structured diff between two calls."""
    call_a_id: str
    call_b_id: str

    # Objections
    new_objections: List[str] = field(default_factory=list)
    resolved_objections: List[str] = field(default_factory=list)
    persistent_objections: List[str] = field(default_factory=list)

    # Topics
    new_topics: List[str] = field(default_factory=list)
    dropped_topics: List[str] = field(default_factory=list)
    common_topics: List[str] = field(default_factory=list)

    # Risk
    risk_a: float = 0.0
    risk_b: float = 0.0
    risk_delta: float = 0.0
    risk_direction: str = "stable"  # up | down | stable

    # Sentiment
    sentiment_shift: Dict[str, Any] = field(default_factory=dict)

    # Signals
    new_signals: List[str] = field(default_factory=list)
    dropped_signals: List[str] = field(default_factory=list)

    # Summary
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_a_id": self.call_a_id,
            "call_b_id": self.call_b_id,
            "objections": {
                "new": self.new_objections,
                "resolved": self.resolved_objections,
                "persistent": self.persistent_objections,
            },
            "topics": {
                "new": self.new_topics,
                "dropped": self.dropped_topics,
                "common": self.common_topics,
            },
            "risk": {
                "call_a": round(self.risk_a, 3),
                "call_b": round(self.risk_b, 3),
                "delta": round(self.risk_delta, 3),
                "direction": self.risk_direction,
                "delta_pct": f"{self.risk_delta:+.0%}",
            },
            "sentiment_shift": self.sentiment_shift,
            "signals": {
                "new": self.new_signals,
                "dropped": self.dropped_signals,
            },
            "summary": self.summary,
        }


def _extract_items(intel: Dict[str, Any], key: str) -> List[str]:
    """Extract a list of items from all segments."""
    items: List[str] = []
    for seg in intel.get("segments", []):
        ext = seg.get("extraction", seg)
        items.extend(ext.get(key, []))
    return items


def _extract_topics(intel: Dict[str, Any]) -> List[str]:
    return [
        seg.get("extraction", seg).get("topic", "general")
        for seg in intel.get("segments", [])
    ]


def _sentiment_distribution(intel: Dict[str, Any]) -> Dict[str, int]:
    counter: Dict[str, int] = {}
    for seg in intel.get("segments", []):
        sent = seg.get("extraction", seg).get("sentiment", "neutral")
        counter[sent] = counter.get(sent, 0) + 1
    return counter


def diff_calls(
    call_a_id: str,
    intel_a: Dict[str, Any],
    call_b_id: str,
    intel_b: Dict[str, Any],
) -> DiffResult:
    """Generate a semantic diff between two calls.

    Call A is the earlier call, Call B is the later call.
    """
    # Objections
    obj_a = set(o.lower().strip() for o in _extract_items(intel_a, "objections"))
    obj_b = set(o.lower().strip() for o in _extract_items(intel_b, "objections"))
    new_obj = sorted(obj_b - obj_a)
    resolved_obj = sorted(obj_a - obj_b)
    persistent_obj = sorted(obj_a & obj_b)

    # Topics
    topics_a = set(t.lower().strip() for t in _extract_topics(intel_a))
    topics_b = set(t.lower().strip() for t in _extract_topics(intel_b))
    new_topics = sorted(topics_b - topics_a)
    dropped_topics = sorted(topics_a - topics_b)
    common_topics = sorted(topics_a & topics_b)

    # Risk
    risk_a = intel_a.get("overall_risk_score", 0.0)
    risk_b = intel_b.get("overall_risk_score", 0.0)
    risk_delta = risk_b - risk_a
    if risk_delta > 0.1:
        risk_direction = "up"
    elif risk_delta < -0.1:
        risk_direction = "down"
    else:
        risk_direction = "stable"

    # Sentiment
    sent_a = _sentiment_distribution(intel_a)
    sent_b = _sentiment_distribution(intel_b)
    all_sentiments = set(list(sent_a.keys()) + list(sent_b.keys()))
    sentiment_shift = {
        s: {"before": sent_a.get(s, 0), "after": sent_b.get(s, 0)}
        for s in sorted(all_sentiments)
    }

    # Signals
    sig_a = set(s.lower().strip() for s in _extract_items(intel_a, "decision_signals"))
    sig_b = set(s.lower().strip() for s in _extract_items(intel_b, "decision_signals"))
    new_signals = sorted(sig_b - sig_a)
    dropped_signals = sorted(sig_a - sig_b)

    # Summary
    parts = []
    if new_obj:
        parts.append(f"{len(new_obj)} new objection(s) raised")
    if resolved_obj:
        parts.append(f"{len(resolved_obj)} objection(s) resolved")
    if risk_direction == "up":
        parts.append(f"risk increased by {abs(risk_delta):.0%}")
    elif risk_direction == "down":
        parts.append(f"risk decreased by {abs(risk_delta):.0%}")
    if new_signals:
        parts.append(f"{len(new_signals)} new decision signal(s)")
    if new_topics:
        parts.append(f"new topics: {', '.join(new_topics[:3])}")

    summary = ". ".join(parts) + "." if parts else "No significant changes between calls."

    return DiffResult(
        call_a_id=call_a_id,
        call_b_id=call_b_id,
        new_objections=new_obj,
        resolved_objections=resolved_obj,
        persistent_objections=persistent_obj,
        new_topics=new_topics,
        dropped_topics=dropped_topics,
        common_topics=common_topics,
        risk_a=risk_a,
        risk_b=risk_b,
        risk_delta=risk_delta,
        risk_direction=risk_direction,
        sentiment_shift=sentiment_shift,
        new_signals=new_signals,
        dropped_signals=dropped_signals,
        summary=summary,
    )
