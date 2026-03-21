"""Deal Risk Agent — monitors risk trends across jobs and fires alerts.

Maintains a rolling risk ledger keyed by (company, deal_id) tuples.
On each new job it compares risk trajectory and emits RiskAlert objects
when thresholds are crossed.

Can be integrated with webhooks to deliver Slack /  email notifications.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Risk thresholds
RISK_HIGH_THRESHOLD = 0.65
RISK_SPIKE_DELTA = 0.20    # alert if risk jumps by this much in one call
MAX_HISTORY = 10           # keep last N risk scores per deal


@dataclass
class RiskAlert:
    job_id: str
    alert_type: str      # "threshold_crossed" | "risk_spike" | "persistent_high"
    risk_score: float
    prev_risk_score: float
    company: str
    objections: List[str]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "alert_type": self.alert_type,
            "risk_score": round(self.risk_score, 3),
            "prev_risk_score": round(self.prev_risk_score, 3),
            "company": self.company,
            "objections": self.objections[:5],
            "message": self.message,
        }


@dataclass
class DealRecord:
    company: str
    deal_id: str
    risk_history: List[float] = field(default_factory=list)
    job_ids: List[str] = field(default_factory=list)

    @property
    def latest_risk(self) -> float:
        return self.risk_history[-1] if self.risk_history else 0.0

    @property
    def trend(self) -> float:
        """Positive = rising risk."""
        if len(self.risk_history) < 2:
            return 0.0
        return self.risk_history[-1] - self.risk_history[-2]

    def add(self, job_id: str, risk: float) -> None:
        self.risk_history.append(risk)
        if len(self.risk_history) > MAX_HISTORY:
            self.risk_history = self.risk_history[-MAX_HISTORY:]
        self.job_ids.append(job_id)


class DealRiskAgent:
    """Tracks risk per deal and emits alerts when thresholds are crossed."""

    def __init__(self) -> None:
        self._deals: Dict[str, DealRecord] = {}   # key: f"{company}::{deal_id}"

    def _key(self, company: str, deal_id: str) -> str:
        return f"{company.lower().strip()}::{deal_id.lower().strip()}"

    def record_job(
        self,
        job_id: str,
        intel: Dict[str, Any],
        company: str = "",
        deal_id: str = "",
    ) -> List[RiskAlert]:
        """Record a new job's risk and return any triggered alerts."""
        key = self._key(company or job_id, deal_id or job_id)

        risk = intel.get("overall_risk_score", 0.0)
        segs = intel.get("segments", [])
        all_obj: List[str] = []
        for s in segs:
            all_obj.extend(s.get("extraction", s).get("objections", []))
        unique_obj = list(dict.fromkeys(all_obj))[:5]

        if key not in self._deals:
            self._deals[key] = DealRecord(company=company or job_id, deal_id=deal_id or job_id)

        record = self._deals[key]
        prev = record.latest_risk
        record.add(job_id, risk)

        alerts: List[RiskAlert] = []

        # Alert 1: crossed HIGH threshold for the first time
        if risk >= RISK_HIGH_THRESHOLD and prev < RISK_HIGH_THRESHOLD:
            alerts.append(RiskAlert(
                job_id=job_id,
                alert_type="threshold_crossed",
                risk_score=risk,
                prev_risk_score=prev,
                company=company or job_id,
                objections=unique_obj,
                message=(
                    f"Deal risk crossed {int(RISK_HIGH_THRESHOLD*100)}% threshold "
                    f"for {company or job_id} (was {round(prev*100)}%, now {round(risk*100)}%). "
                    f"Objections: {'; '.join(unique_obj) or 'none'}."
                ),
            ))

        # Alert 2: sudden risk spike
        if (risk - prev) >= RISK_SPIKE_DELTA and prev > 0:
            alerts.append(RiskAlert(
                job_id=job_id,
                alert_type="risk_spike",
                risk_score=risk,
                prev_risk_score=prev,
                company=company or job_id,
                objections=unique_obj,
                message=(
                    f"Risk spike detected for {company or job_id}: "
                    f"+{round((risk - prev)*100)}% in one call "
                    f"({round(prev*100)}% → {round(risk*100)}%)."
                ),
            ))

        # Alert 3: persistently high risk for 3+ calls
        if (len(record.risk_history) >= 3
                and all(r >= RISK_HIGH_THRESHOLD for r in record.risk_history[-3:])):
            # Only fire once per job to avoid spam
            alerts.append(RiskAlert(
                job_id=job_id,
                alert_type="persistent_high",
                risk_score=risk,
                prev_risk_score=prev,
                company=company or job_id,
                objections=unique_obj,
                message=(
                    f"Persistent high-risk deal: {company or job_id} has been "
                    f"≥{int(RISK_HIGH_THRESHOLD*100)}% risk for 3 consecutive calls."
                ),
            ))

        return alerts

    def run_sweep(self) -> List[RiskAlert]:
        """Return alerts for all currently tracked high-risk deals."""
        alerts: List[RiskAlert] = []
        for record in self._deals.values():
            if record.latest_risk >= RISK_HIGH_THRESHOLD:
                alerts.append(RiskAlert(
                    job_id=record.job_ids[-1] if record.job_ids else "",
                    alert_type="persistent_high",
                    risk_score=record.latest_risk,
                    prev_risk_score=record.risk_history[-2] if len(record.risk_history) > 1 else 0.0,
                    company=record.company,
                    objections=[],
                    message=(
                        f"{record.company} deal is HIGH risk: "
                        f"{round(record.latest_risk * 100)}% | "
                        f"trend: {'↑' if record.trend > 0 else '↓' if record.trend < 0 else '→'}"
                    ),
                ))
        return alerts

    def get_deal_summary(self, company: str, deal_id: str = "") -> Optional[Dict[str, Any]]:
        key = self._key(company, deal_id)
        r = self._deals.get(key)
        if not r:
            return None
        return {
            "company": r.company,
            "deal_id": r.deal_id,
            "latest_risk": round(r.latest_risk, 3),
            "trend": round(r.trend, 3),
            "calls_analyzed": len(r.job_ids),
            "risk_history": [round(x, 3) for x in r.risk_history],
        }

    def list_deals(self) -> List[Dict[str, Any]]:
        return [
            {
                "company": r.company,
                "deal_id": r.deal_id,
                "latest_risk": round(r.latest_risk, 3),
                "trend": round(r.trend, 3),
                "calls": len(r.job_ids),
            }
            for r in sorted(self._deals.values(), key=lambda x: -x.latest_risk)
        ]


_agent: Optional[DealRiskAgent] = None


def get_risk_agent() -> DealRiskAgent:
    global _agent
    if _agent is None:
        _agent = DealRiskAgent()
    return _agent
