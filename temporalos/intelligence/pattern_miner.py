"""Cross-Call Pattern Mining — discover statistical patterns across video library.

Finds correlations like:
- "Calls mentioning competitor X close 30% less"
- "Reps asking 5+ questions have 2x win rate"
- "Pricing discussed in first 5 min → higher risk"
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    """A discovered statistical pattern."""
    id: str
    description: str
    category: str  # objection | topic | rep | risk | signal
    metric: str
    value: float
    sample_size: int
    significance: str  # high | medium | low
    insight: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "category": self.category,
            "metric": self.metric,
            "value": round(self.value, 3),
            "sample_size": self.sample_size,
            "significance": self.significance,
            "insight": self.insight,
        }


class PatternMiner:
    """Discovers statistical patterns across a library of processed calls."""

    def __init__(self) -> None:
        self._calls: List[Dict[str, Any]] = []

    def add_call(self, job_id: str, intel: Dict[str, Any],
                 company: str = "", rep: str = "", outcome: str = "") -> None:
        """Register a call for pattern mining."""
        segments = intel.get("segments", [])
        all_obj = []
        all_signals = []
        all_topics = []
        risk_scores = []

        for seg in segments:
            ext = seg.get("extraction", seg)
            all_obj.extend(ext.get("objections", []))
            all_signals.extend(ext.get("decision_signals", []))
            all_topics.append(ext.get("topic", "general"))
            risk_scores.append(ext.get("risk_score", 0.0))

        speaker_intel = intel.get("speaker_intelligence", {})
        talk_ratio = speaker_intel.get("talk_ratio", {}).get("SPEAKER_A", 0.5)
        stats = speaker_intel.get("speaker_stats", {}).get("SPEAKER_A", {})
        questions = stats.get("question_count", 0)
        wpm = stats.get("words_per_minute", 140)

        self._calls.append({
            "job_id": job_id,
            "company": company,
            "rep": rep,
            "outcome": outcome,
            "risk": intel.get("overall_risk_score", 0.0),
            "objections": [o.lower().strip() for o in all_obj],
            "signals": [s.lower().strip() for s in all_signals],
            "topics": [t.lower().strip() for t in all_topics],
            "talk_ratio": talk_ratio,
            "questions": questions,
            "wpm": wpm,
            "segment_count": len(segments),
        })

    def mine_patterns(self, min_sample_size: int = 3) -> List[Pattern]:
        """Run all pattern miners and return discovered patterns."""
        patterns: List[Pattern] = []
        if len(self._calls) < min_sample_size:
            return patterns

        patterns.extend(self._mine_objection_patterns(min_sample_size))
        patterns.extend(self._mine_topic_patterns(min_sample_size))
        patterns.extend(self._mine_rep_patterns(min_sample_size))
        patterns.extend(self._mine_behavior_patterns())

        # Sort by significance
        sig_order = {"high": 0, "medium": 1, "low": 2}
        patterns.sort(key=lambda p: sig_order.get(p.significance, 3))
        return patterns

    def _mine_objection_patterns(self, min_n: int) -> List[Pattern]:
        """Find which objections correlate with higher/lower risk."""
        patterns = []
        obj_counter: Counter = Counter()
        obj_risk: Dict[str, List[float]] = defaultdict(list)

        for call in self._calls:
            for obj in set(call["objections"]):
                obj_counter[obj] += 1
                obj_risk[obj].append(call["risk"])

        avg_risk = sum(c["risk"] for c in self._calls) / len(self._calls)

        for obj, count in obj_counter.most_common(10):
            if count < min_n:
                continue
            risks = obj_risk[obj]
            avg = sum(risks) / len(risks)
            delta = avg - avg_risk

            if abs(delta) > 0.1:
                direction = "higher" if delta > 0 else "lower"
                patterns.append(Pattern(
                    id=f"obj_{obj[:20]}",
                    description=f'Calls with objection "{obj}" have {abs(delta):.0%} {direction} risk',
                    category="objection",
                    metric="risk_delta",
                    value=delta,
                    sample_size=count,
                    significance="high" if abs(delta) > 0.2 else "medium",
                    insight=f'When "{obj}" comes up, average risk is {avg:.0%} vs baseline {avg_risk:.0%}.',
                ))

        return patterns

    def _mine_topic_patterns(self, min_n: int) -> List[Pattern]:
        """Find topic-risk correlations."""
        patterns = []
        topic_risk: Dict[str, List[float]] = defaultdict(list)

        for call in self._calls:
            for topic in set(call["topics"]):
                topic_risk[topic].append(call["risk"])

        avg_risk = sum(c["risk"] for c in self._calls) / len(self._calls)

        for topic, risks in topic_risk.items():
            if len(risks) < min_n:
                continue
            avg = sum(risks) / len(risks)
            delta = avg - avg_risk
            if abs(delta) > 0.1:
                direction = "riskier" if delta > 0 else "safer"
                patterns.append(Pattern(
                    id=f"topic_{topic[:20]}",
                    description=f'Calls discussing "{topic}" are {abs(delta):.0%} {direction}',
                    category="topic",
                    metric="risk_delta",
                    value=delta,
                    sample_size=len(risks),
                    significance="high" if abs(delta) > 0.2 else "medium",
                    insight=f'Topic "{topic}": avg risk {avg:.0%} vs baseline {avg_risk:.0%}.',
                ))

        return patterns

    def _mine_rep_patterns(self, min_n: int) -> List[Pattern]:
        """Find per-rep performance patterns."""
        patterns = []
        rep_data: Dict[str, List[Dict]] = defaultdict(list)

        for call in self._calls:
            if call["rep"]:
                rep_data[call["rep"]].append(call)

        if len(rep_data) < 2:
            return patterns

        avg_risk = sum(c["risk"] for c in self._calls) / len(self._calls)

        for rep, calls in rep_data.items():
            if len(calls) < min_n:
                continue
            avg_rep_risk = sum(c["risk"] for c in calls) / len(calls)
            avg_questions = sum(c["questions"] for c in calls) / len(calls)

            delta = avg_risk - avg_rep_risk  # positive = better (lower risk)
            if abs(delta) > 0.08:
                performance = "outperforms" if delta > 0 else "underperforms"
                patterns.append(Pattern(
                    id=f"rep_{rep[:20]}",
                    description=f'{rep} {performance} average by {abs(delta):.0%} risk',
                    category="rep",
                    metric="risk_vs_avg",
                    value=delta,
                    sample_size=len(calls),
                    significance="medium",
                    insight=f'{rep}: avg risk {avg_rep_risk:.0%}, {len(calls)} calls, '
                            f'avg {avg_questions:.1f} questions/call.',
                ))

        return patterns

    def _mine_behavior_patterns(self) -> List[Pattern]:
        """Find behavioral patterns (talk ratio, questions, pace)."""
        patterns = []
        if len(self._calls) < 5:
            return patterns

        # Question count vs risk
        high_q = [c for c in self._calls if c["questions"] >= 5]
        low_q = [c for c in self._calls if c["questions"] < 3]
        if len(high_q) >= 3 and len(low_q) >= 3:
            avg_high_q_risk = sum(c["risk"] for c in high_q) / len(high_q)
            avg_low_q_risk = sum(c["risk"] for c in low_q) / len(low_q)
            delta = avg_low_q_risk - avg_high_q_risk
            if delta > 0.05:
                patterns.append(Pattern(
                    id="behavior_questions",
                    description=f"Reps asking 5+ questions have {delta:.0%} lower risk",
                    category="behavior",
                    metric="question_risk_delta",
                    value=delta,
                    sample_size=len(high_q) + len(low_q),
                    significance="high" if delta > 0.15 else "medium",
                    insight=f"High-question calls: {avg_high_q_risk:.0%} risk. "
                            f"Low-question calls: {avg_low_q_risk:.0%} risk.",
                ))

        # Talk ratio
        balanced = [c for c in self._calls if 0.35 <= c["talk_ratio"] <= 0.55]
        imbalanced = [c for c in self._calls if c["talk_ratio"] > 0.6]
        if len(balanced) >= 3 and len(imbalanced) >= 3:
            avg_bal_risk = sum(c["risk"] for c in balanced) / len(balanced)
            avg_imb_risk = sum(c["risk"] for c in imbalanced) / len(imbalanced)
            delta = avg_imb_risk - avg_bal_risk
            if delta > 0.05:
                patterns.append(Pattern(
                    id="behavior_talk_ratio",
                    description=f"Reps talking >60% have {delta:.0%} higher risk",
                    category="behavior",
                    metric="talk_ratio_risk_delta",
                    value=delta,
                    sample_size=len(balanced) + len(imbalanced),
                    significance="medium",
                    insight=f"Balanced calls: {avg_bal_risk:.0%} risk. "
                            f"Over-talking calls: {avg_imb_risk:.0%} risk.",
                ))

        return patterns

    @property
    def call_count(self) -> int:
        return len(self._calls)


_miner: Optional[PatternMiner] = None


def get_pattern_miner() -> PatternMiner:
    global _miner
    if _miner is None:
        _miner = PatternMiner()
    return _miner
