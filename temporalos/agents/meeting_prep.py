"""Meeting Prep Agent — generates bespoke pre-call briefs.

Searches the video library for prior calls with the same company / contact,
extracts recurring topics, unresolved objections, and open action items,
then composes a structured meeting brief.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from temporalos.agents.vector_store import TFIDFStore, Document

logger = logging.getLogger(__name__)


@dataclass
class MeetingBrief:
    company: str
    contact: str
    prior_calls: int
    open_objections: List[str]
    recurring_topics: List[str]
    open_action_items: List[str]
    risk_trajectory: str         # "rising" | "falling" | "stable" | "new"
    last_risk_score: float
    talking_points: List[str]
    watch_outs: List[str]
    raw_excerpts: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "contact": self.contact,
            "prior_calls": self.prior_calls,
            "open_objections": self.open_objections,
            "recurring_topics": self.recurring_topics,
            "open_action_items": self.open_action_items,
            "risk_trajectory": self.risk_trajectory,
            "last_risk_score": round(self.last_risk_score, 3),
            "risk_pct": round(self.last_risk_score * 100),
            "talking_points": self.talking_points,
            "watch_outs": self.watch_outs,
            "raw_excerpts": self.raw_excerpts[:3],
        }


class MeetingPrepAgent:
    """Generates pre-meeting briefs from historical video intelligence."""

    def __init__(self) -> None:
        self._store = TFIDFStore()
        # company_key → list of job metadata
        self._company_index: Dict[str, List[Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_job(
        self,
        job_id: str,
        intel: Dict[str, Any],
        company: str = "",
        contact: str = "",
    ) -> None:
        """Index a completed job for future meeting prep lookup."""
        company_key = (company or job_id).lower().strip()
        segs = intel.get("segments", [])

        all_obj: List[str] = []
        all_signals: List[str] = []
        topics: List[str] = []
        for s in segs:
            ext = s.get("extraction", s)
            all_obj.extend(ext.get("objections", []))
            all_signals.extend(ext.get("decision_signals", []))
            topics.append(ext.get("topic", "general"))

        # Store metadata summary
        record: Dict[str, Any] = {
            "job_id": job_id,
            "company": company,
            "contact": contact,
            "objections": list(dict.fromkeys(all_obj)),
            "signals": list(dict.fromkeys(all_signals)),
            "topics": list(dict.fromkeys(topics)),
            "risk": intel.get("overall_risk_score", 0.0),
        }
        if company_key not in self._company_index:
            self._company_index[company_key] = []
        self._company_index[company_key].append(record)

        # Also index into TF-IDF for free-text search
        text = " ".join([company, contact] + all_obj + all_signals + topics)
        self._store.add(Document(
            id=job_id,
            text=text,
            metadata=record,
        ))

    # ------------------------------------------------------------------
    # Brief generation
    # ------------------------------------------------------------------

    def generate_brief(
        self,
        company: str,
        contact: str = "",
        use_search: bool = True,
    ) -> MeetingBrief:
        """Generate a meeting prep brief for an upcoming call."""
        company_key = company.lower().strip()
        prior_records: List[Dict[str, Any]] = self._company_index.get(company_key, [])

        # Fall back to semantic search if no direct company match
        if not prior_records and use_search:
            hits = self._store.search(f"{company} {contact}".strip(), top_k=10)
            prior_records = [doc.metadata for doc, _ in hits]

        if not prior_records:
            return MeetingBrief(
                company=company,
                contact=contact,
                prior_calls=0,
                open_objections=[],
                recurring_topics=[],
                open_action_items=[],
                risk_trajectory="new",
                last_risk_score=0.0,
                talking_points=["Introduce TemporalOS capabilities.",
                                 "Understand current workflow pain points.",
                                 "Discuss integration requirements."],
                watch_outs=["No prior history — qualify budget and timeline early."],
                raw_excerpts=[],
            )

        n = len(prior_records)

        # Aggregate across prior calls
        all_obj: List[str] = []
        all_signals: List[str] = []
        all_topics: List[str] = []
        risk_scores: List[float] = []
        excerpts: List[Dict[str, Any]] = []

        for rec in prior_records[-10:]:  # last 10 calls
            all_obj.extend(rec.get("objections", []))
            all_signals.extend(rec.get("signals", []))
            all_topics.extend(rec.get("topics", []))
            risk_scores.append(rec.get("risk", 0.0))
            excerpts.append({"job_id": rec.get("job_id"), "risk": rec.get("risk")})

        # Frequency-ranked unique items
        from collections import Counter
        obj_counted = Counter(all_obj)
        topic_counted = Counter(all_topics)
        sig_counted = Counter(all_signals)

        recurring_obj = [obj for obj, _ in obj_counted.most_common(5)]
        recurring_topics = [t for t, _ in topic_counted.most_common(5)]
        open_signals = [s for s, _ in sig_counted.most_common(5)]

        # Risk trajectory
        last_risk = risk_scores[-1] if risk_scores else 0.0
        if len(risk_scores) < 2:
            trajectory = "new" if not risk_scores else "stable"
        else:
            delta = risk_scores[-1] - risk_scores[-2]
            if delta > 0.10:
                trajectory = "rising"
            elif delta < -0.10:
                trajectory = "falling"
            else:
                trajectory = "stable"

        # Compose talking points
        talking_points: List[str] = []
        if open_signals:
            talking_points.append(f"Follow up on: {'; '.join(open_signals[:2])}.")
        if recurring_topics:
            talking_points.append(f"Revisit key themes: {', '.join(recurring_topics[:3])}.")
        if not talking_points:
            talking_points.append("Review progress since last call.")
        talking_points.append("Confirm next steps and timeline.")

        # Watch-outs
        watch_outs: List[str] = []
        if recurring_obj:
            watch_outs.append(f"Recurring objections: {'; '.join(recurring_obj[:3])} — prepare responses.")
        if trajectory == "rising":
            watch_outs.append(f"Risk trending UP ({round(last_risk * 100)}%) — probe for blocking issues.")
        if not watch_outs:
            watch_outs.append("Stable deal — focus on accelerating timeline.")

        return MeetingBrief(
            company=company,
            contact=contact,
            prior_calls=n,
            open_objections=recurring_obj,
            recurring_topics=recurring_topics,
            open_action_items=open_signals,
            risk_trajectory=trajectory,
            last_risk_score=last_risk,
            talking_points=talking_points,
            watch_outs=watch_outs,
            raw_excerpts=excerpts[-3:],
        )

    @property
    def indexed_companies(self) -> List[str]:
        return sorted(self._company_index.keys())


_agent: Optional[MeetingPrepAgent] = None


def get_meeting_prep_agent() -> MeetingPrepAgent:
    global _agent
    if _agent is None:
        _agent = MeetingPrepAgent()
    return _agent
