"""Live Call Copilot — real-time coaching prompts during live calls.

Analyzes streaming segments and generates:
- Battlecard prompts when competitor mentioned
- Risk warnings when score spikes
- Question suggestions when talk ratio imbalanced
- Closing prompts when signals detected
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CopilotPrompt:
    """A real-time coaching prompt."""
    type: str  # battlecard | risk_warning | question_hint | closing_prompt | pace_alert
    title: str
    message: str
    priority: str  # high | medium | low
    timestamp_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "timestamp_ms": self.timestamp_ms,
            "metadata": self.metadata,
        }


# Competitor battlecards
BATTLECARDS: Dict[str, Dict[str, str]] = {
    "gong": {
        "title": "Competitor: Gong",
        "message": "Gong is post-call only. Highlight our real-time analysis and live copilot. "
                   "Our temporal alignment is unique — frame-by-frame visual + audio sync.",
    },
    "chorus": {
        "title": "Competitor: Chorus (ZoomInfo)",
        "message": "Chorus focuses on conversation analytics. We go beyond with vision AI, "
                   "knowledge graph, and multi-vertical support (not just sales).",
    },
    "clari": {
        "title": "Competitor: Clari",
        "message": "Clari is a revenue platform, not conversation intelligence. "
                   "We provide deeper extraction with real-time structured output.",
    },
}

COMPETITOR_KEYWORDS: Dict[str, List[str]] = {
    "gong": ["gong", "gong.io"],
    "chorus": ["chorus", "chorus.ai", "zoominfo"],
    "clari": ["clari"],
}


class LiveCopilot:
    """Real-time coaching engine for live calls."""

    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []
        self._prompts: List[CopilotPrompt] = []
        self._talk_ratio_a = 0.0
        self._segment_count = 0
        self._total_risk = 0.0

    def process_segment(self, segment: Dict[str, Any]) -> List[CopilotPrompt]:
        """Process a new streaming segment, return any coaching prompts."""
        self._segment_count += 1
        self._history.append(segment)
        prompts: List[CopilotPrompt] = []

        ext = segment.get("extraction", segment)
        ts = segment.get("timestamp_ms", 0)
        transcript = segment.get("transcript", "").lower()
        risk = ext.get("risk_score", 0.0)
        self._total_risk += risk

        # Competitor detection → battlecard
        for competitor, keywords in COMPETITOR_KEYWORDS.items():
            if any(kw in transcript for kw in keywords):
                card = BATTLECARDS.get(competitor, {})
                prompts.append(CopilotPrompt(
                    type="battlecard",
                    title=card.get("title", f"Competitor: {competitor}"),
                    message=card.get("message", f"Competitor {competitor} mentioned."),
                    priority="high",
                    timestamp_ms=ts,
                    metadata={"competitor": competitor},
                ))

        # Risk spike warning
        if risk > 0.7:
            prompts.append(CopilotPrompt(
                type="risk_warning",
                title="Risk Spike Detected",
                message=f"Risk score at {risk:.0%}. Consider probing for blockers: "
                        "'What concerns do you still have?' or 'What would need to be true for you to move forward?'",
                priority="high",
                timestamp_ms=ts,
                metadata={"risk_score": risk},
            ))

        # Objection detected
        objections = ext.get("objections", [])
        if objections:
            prompts.append(CopilotPrompt(
                type="objection_alert",
                title="Objection Raised",
                message=f"Objection: '{objections[0]}'. Use Feel-Felt-Found: "
                        "'I understand how you feel. Other customers felt the same way. "
                        "What they found was...'",
                priority="medium",
                timestamp_ms=ts,
                metadata={"objections": objections},
            ))

        # Decision signal → closing prompt
        signals = ext.get("decision_signals", [])
        if signals:
            prompts.append(CopilotPrompt(
                type="closing_prompt",
                title="Buying Signal Detected",
                message=f"Signal: '{signals[0]}'. This is a buying moment. "
                        "Ask for the next step: 'Would you like me to prepare a proposal?'",
                priority="high",
                timestamp_ms=ts,
                metadata={"signals": signals},
            ))

        # Talk ratio check (every 5 segments)
        if self._segment_count % 5 == 0:
            speaker_intel = segment.get("speaker_intelligence", {})
            talk_ratio = speaker_intel.get("talk_ratio", {}).get("SPEAKER_A", 0.5)
            if talk_ratio > 0.65:
                prompts.append(CopilotPrompt(
                    type="pace_alert",
                    title="Listening Reminder",
                    message=f"You're at {talk_ratio:.0%} talk time. "
                            "Ask an open-ended question to let the prospect share more.",
                    priority="low",
                    timestamp_ms=ts,
                ))

        self._prompts.extend(prompts)
        return prompts

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of copilot session."""
        avg_risk = self._total_risk / max(self._segment_count, 1)
        prompt_types = {}
        for p in self._prompts:
            prompt_types[p.type] = prompt_types.get(p.type, 0) + 1

        return {
            "segments_processed": self._segment_count,
            "total_prompts": len(self._prompts),
            "prompt_types": prompt_types,
            "avg_risk": round(avg_risk, 3),
            "prompts": [p.to_dict() for p in self._prompts],
        }

    def reset(self) -> None:
        self._history.clear()
        self._prompts.clear()
        self._segment_count = 0
        self._total_risk = 0.0
