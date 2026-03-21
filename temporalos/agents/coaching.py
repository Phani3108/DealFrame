"""Coaching Engine — generates per-rep, data-driven coaching cards.

Aggregates speaker intelligence and extraction results across all calls
for a rep (identified by speaker name or rep_id) and produces:
  - Talk ratio benchmark vs top quartile
  - WPM (words per minute) benchmark
  - Filler word rate
  - Question frequency
  - Objection handling success rate
  - Top improvement action items
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Benchmark targets (top-quartile reps from industry research)
BENCHMARK = {
    "talk_ratio_max": 0.55,          # Rep should talk ≤55% of the time
    "words_per_minute_range": (120, 160),  # Natural pace range
    "filler_rate_max": 0.03,          # <3 % filler words
    "questions_per_segment_min": 1.5,  # Ask ≥1.5 questions per segment
}


@dataclass
class CoachingDimension:
    name: str
    score: float          # 0.0 – 1.0 (higher = better)
    value: float          # raw measured value
    benchmark: float      # target value
    verdict: str          # "excellent" | "good" | "needs_work"
    tip: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "value": round(self.value, 3),
            "benchmark": round(self.benchmark, 3),
            "verdict": self.verdict,
            "tip": self.tip,
        }


@dataclass
class CoachingCard:
    rep_id: str
    calls_analyzed: int
    overall_score: float
    dimensions: List[CoachingDimension] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    example_moments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rep_id": self.rep_id,
            "calls_analyzed": self.calls_analyzed,
            "overall_score": round(self.overall_score, 2),
            "grade": self._grade(),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "strengths": self.strengths,
            "improvements": self.improvements,
            "example_moments": self.example_moments[:3],
        }

    def _grade(self) -> str:
        if self.overall_score >= 0.85:
            return "A"
        if self.overall_score >= 0.70:
            return "B"
        if self.overall_score >= 0.55:
            return "C"
        return "D"


class CoachingEngine:
    """Generates coaching cards from accumulated speaker + extraction data."""

    def __init__(self) -> None:
        # rep_id → list of call records
        self._rep_data: Dict[str, List[Dict[str, Any]]] = {}

    def record_call(
        self,
        rep_id: str,
        job_id: str,
        intel: Dict[str, Any],
        speaker_label: str = "SPEAKER_A",
    ) -> None:
        """Register a completed call for a rep."""
        if rep_id not in self._rep_data:
            self._rep_data[rep_id] = []

        talk_ratio = 0.0
        wpm = 0.0
        filler_rate = 0.0
        questions = 0
        objections_handled = 0
        segments = intel.get("segments", [])

        speaker_intel = intel.get("speaker_intelligence", {})
        if speaker_intel:
            stats = speaker_intel.get("speaker_stats", {}).get(speaker_label, {})
            talk_ratio = speaker_intel.get("talk_ratio", {}).get(speaker_label, 0.0)
            wpm = stats.get("words_per_minute", 0.0)
            filler_rate = stats.get("filler_rate", 0.0)
            questions = stats.get("question_count", 0)
        else:
            # Heuristic: estimate from segment count
            talk_ratio = 0.5
            wpm = 140.0
            questions = max(1, len(segments) // 3)

        all_obj: List[str] = []
        handled_signals: List[str] = []
        for s in segments:
            ext = s.get("extraction", s)
            all_obj.extend(ext.get("objections", []))
            handled_signals.extend(ext.get("decision_signals", []))

        # Objection handling score: if signals present after objection → handled
        if all_obj:
            objections_handled = min(len(handled_signals), len(all_obj))

        self._rep_data[rep_id].append({
            "job_id": job_id,
            "talk_ratio": talk_ratio,
            "wpm": wpm,
            "filler_rate": filler_rate,
            "questions_per_segment": questions / max(len(segments), 1),
            "objection_count": len(all_obj),
            "objections_handled": objections_handled,
            "high_risk_segments": [
                {"job_id": job_id, "timestamp": s.get("timestamp_str"), "topic": s.get("extraction", s).get("topic")}
                for s in segments if s.get("extraction", s).get("risk_score", 0) > 0.65
            ],
        })

    def generate_coaching_card(self, rep_id: str) -> Optional[CoachingCard]:
        calls = self._rep_data.get(rep_id)
        if not calls:
            return None

        n = len(calls)

        # Average across all calls
        avg_talk_ratio = sum(c["talk_ratio"] for c in calls) / n
        avg_wpm = sum(c["wpm"] for c in calls) / n
        avg_filler = sum(c["filler_rate"] for c in calls) / n
        avg_qps = sum(c["questions_per_segment"] for c in calls) / n
        total_obj = sum(c["objection_count"] for c in calls)
        total_handled = sum(c["objections_handled"] for c in calls)
        obj_rate = (total_handled / total_obj) if total_obj > 0 else 1.0

        # Build dimensions
        dims: List[CoachingDimension] = []

        # Talk ratio
        tr_score = 1.0 - max(0.0, avg_talk_ratio - BENCHMARK["talk_ratio_max"])
        dims.append(CoachingDimension(
            name="Talk Ratio",
            score=min(1.0, tr_score),
            value=avg_talk_ratio,
            benchmark=BENCHMARK["talk_ratio_max"],
            verdict="excellent" if avg_talk_ratio <= 0.45 else "good" if avg_talk_ratio <= 0.55 else "needs_work",
            tip="Try listening more — let the prospect talk ≥45% of the time.",
        ))

        # WPM
        lo, hi = BENCHMARK["words_per_minute_range"]
        wpm_score = 1.0 if lo <= avg_wpm <= hi else max(0.0, 1.0 - abs(avg_wpm - ((lo + hi) / 2)) / 60)
        dims.append(CoachingDimension(
            name="Speaking Pace",
            score=wpm_score,
            value=avg_wpm,
            benchmark=(lo + hi) / 2,
            verdict="good" if lo <= avg_wpm <= hi else "needs_work",
            tip=f"Aim for {lo}–{hi} WPM. {'Slow down a little.' if avg_wpm > hi else 'Pick up the pace slightly.'}",
        ))

        # Filler words
        filler_score = max(0.0, 1.0 - avg_filler / BENCHMARK["filler_rate_max"])
        dims.append(CoachingDimension(
            name="Filler Words",
            score=min(1.0, 1.0 - avg_filler * 10),
            value=avg_filler,
            benchmark=BENCHMARK["filler_rate_max"],
            verdict="excellent" if avg_filler < 0.01 else "good" if avg_filler < 0.03 else "needs_work",
            tip="Replace filler words ('um', 'like') with intentional pauses.",
        ))

        # Questioning frequency
        qps_score = min(1.0, avg_qps / BENCHMARK["questions_per_segment_min"])
        dims.append(CoachingDimension(
            name="Discovery Questions",
            score=qps_score,
            value=avg_qps,
            benchmark=BENCHMARK["questions_per_segment_min"],
            verdict="excellent" if avg_qps >= 2.0 else "good" if avg_qps >= 1.5 else "needs_work",
            tip="Ask more open-ended discovery questions to uncover real pain.",
        ))

        # Objection handling
        dims.append(CoachingDimension(
            name="Objection Handling",
            score=obj_rate,
            value=obj_rate,
            benchmark=0.7,
            verdict="excellent" if obj_rate >= 0.8 else "good" if obj_rate >= 0.6 else "needs_work",
            tip="Acknowledge objections before countering — use the 'Feel-Felt-Found' framework.",
        ))

        overall = sum(d.score for d in dims) / len(dims)
        strengths = [d.name for d in dims if d.score >= 0.75]
        improvements = [d.tip for d in dims if d.score < 0.65]

        # Sample high-risk moments for review
        moments: List[Dict[str, Any]] = []
        for c in calls[-5:]:
            moments.extend(c.get("high_risk_segments", []))

        return CoachingCard(
            rep_id=rep_id,
            calls_analyzed=n,
            overall_score=overall,
            dimensions=dims,
            strengths=strengths or ["Consistent engagement across all calls."],
            improvements=improvements or ["Keep up the great work!"],
            example_moments=moments[:3],
        )

    def list_reps(self) -> List[str]:
        return sorted(self._rep_data.keys())


_engine: Optional[CoachingEngine] = None


def get_coaching_engine() -> CoachingEngine:
    global _engine
    if _engine is None:
        _engine = CoachingEngine()
    return _engine
