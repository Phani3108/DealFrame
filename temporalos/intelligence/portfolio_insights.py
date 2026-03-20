"""Higher-order portfolio analytics: win/loss patterns, objection velocity, rep comparison.

All methods operate on plain dicts (not ORM models) for broad testability.
In production, callers build the `extractions` list by querying the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WinLossPattern:
    high_risk_objections: list[str]
    low_risk_topics: list[str]
    avg_risk_score: float
    risk_distribution: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "high_risk_objections": self.high_risk_objections,
            "low_risk_topics": self.low_risk_topics,
            "avg_risk_score": round(self.avg_risk_score, 3),
            "risk_distribution": self.risk_distribution,
        }


@dataclass
class ObjectionVelocity:
    objection: str
    counts_by_period: list[dict]  # [{"period": "2026-W10", "count": 5}, ...]
    trend: str  # rising | falling | stable

    def to_dict(self) -> dict:
        return {
            "objection": self.objection,
            "trend": self.trend,
            "counts_by_period": self.counts_by_period,
        }


class PortfolioInsights:
    """
    Derives higher-order intelligence from a collection of extraction result dicts.

    Expected dict shape (matches ExtractionResult.to_dict() + created_at):
        {"topic": str, "risk": str, "risk_score": float,
         "objections": [str], "decision_signals": [str], "created_at": str}
    """

    @staticmethod
    def win_loss_patterns(extractions: list[dict]) -> WinLossPattern:
        """Identify which objections and topics correlate with high / low risk."""
        if not extractions:
            return WinLossPattern([], [], 0.0, {"high": 0, "medium": 0, "low": 0})

        risk_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        total_risk = 0.0
        high_risk_obj: dict[str, int] = {}
        low_risk_topics: dict[str, int] = {}

        for e in extractions:
            risk = e.get("risk", "low")
            risk_dist[risk] = risk_dist.get(risk, 0) + 1
            total_risk += float(e.get("risk_score", 0.0))

            if risk == "high":
                for obj in e.get("objections", []):
                    high_risk_obj[obj] = high_risk_obj.get(obj, 0) + 1
            elif risk == "low":
                topic = e.get("topic", "")
                if topic:
                    low_risk_topics[topic] = low_risk_topics.get(topic, 0) + 1

        sorted_objs = sorted(high_risk_obj, key=lambda k: high_risk_obj[k], reverse=True)
        sorted_topics = sorted(low_risk_topics, key=lambda k: low_risk_topics[k], reverse=True)

        return WinLossPattern(
            high_risk_objections=sorted_objs[:5],
            low_risk_topics=sorted_topics[:5],
            avg_risk_score=total_risk / len(extractions),
            risk_distribution=risk_dist,
        )

    @staticmethod
    def objection_velocity(
        extractions: list[dict],
        period: str = "week",
    ) -> list[ObjectionVelocity]:
        """Track how objection frequency changes over time periods."""
        from collections import defaultdict

        period_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for e in extractions:
            created_at = e.get("created_at", "")
            try:
                dt = datetime.fromisoformat(str(created_at))
                key = dt.strftime("%Y-W%V") if period == "week" else dt.strftime("%Y-%m")
            except (ValueError, TypeError):
                key = "unknown"
            for obj in e.get("objections", []):
                period_counts[obj][key] += 1

        results: list[ObjectionVelocity] = []
        for obj, p_counts in period_counts.items():
            periods = sorted(p_counts.keys())
            counts = [p_counts[p] for p in periods]
            if len(counts) >= 2:
                mid = len(counts) // 2
                first = sum(counts[:mid]) / max(mid, 1)
                second = sum(counts[mid:]) / max(len(counts) - mid, 1)
                if second > first * 1.2:
                    trend = "rising"
                elif second < first * 0.8:
                    trend = "falling"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            results.append(
                ObjectionVelocity(
                    objection=obj,
                    counts_by_period=[
                        {"period": p, "count": c} for p, c in zip(periods, counts)
                    ],
                    trend=trend,
                )
            )

        return sorted(
            results,
            key=lambda r: sum(c["count"] for c in r.counts_by_period),
            reverse=True,
        )

    @staticmethod
    def rep_comparison(extractions_by_rep: dict[str, list[dict]]) -> dict:
        """Compare extraction metrics across sales reps or video sources."""
        comparison: dict[str, dict] = {}
        for rep, extractions in extractions_by_rep.items():
            if not extractions:
                continue
            n = len(extractions)
            avg_risk = sum(float(e.get("risk_score", 0)) for e in extractions) / n
            high_risk = sum(1 for e in extractions if e.get("risk") == "high")
            obj_count = sum(len(e.get("objections", [])) for e in extractions)
            signal_count = sum(len(e.get("decision_signals", [])) for e in extractions)
            comparison[rep] = {
                "segment_count": n,
                "avg_risk_score": round(avg_risk, 3),
                "high_risk_segments": high_risk,
                "avg_objections_per_segment": round(obj_count / n, 2),
                "avg_signals_per_segment": round(signal_count / n, 2),
            }
        return comparison
