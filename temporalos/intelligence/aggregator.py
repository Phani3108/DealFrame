"""
Multi-video intelligence aggregator — Phase 3.

Aggregates extraction results across multiple processed videos to produce
portfolio-level intelligence: top objections, topic frequency trends,
risk score timelines, and competitor mention counts.

REST API (Phase 3):
  GET /api/v1/intelligence/objections?portfolio=Q1&limit=10
  GET /api/v1/intelligence/topics/trend?days=30
  GET /api/v1/intelligence/risk/summary
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ObjectionSummary:
    text: str
    count: int
    example_timestamps: list[str] = field(default_factory=list)
    risk_avg: float = 0.0


@dataclass
class TopicTrend:
    topic: str
    counts_by_day: dict[str, int] = field(default_factory=dict)


@dataclass
class PortfolioRiskSummary:
    portfolio_id: str
    video_count: int
    avg_risk_score: float
    high_risk_video_count: int
    top_risk_topics: list[str] = field(default_factory=list)


class VideoAggregator:
    """
    Phase 3 — Multi-video Intelligence.

    Queries the extractions table to build cross-video analytics.
    Runs against the SQLAlchemy session — no external services needed.

    Usage (Phase 3):
        aggregator = VideoAggregator(session)
        objections = await aggregator.top_objections(portfolio_id="Q1", limit=10)
        trends = await aggregator.topic_trends(days=30)
        risk = await aggregator.risk_summary(portfolio_id="Q1")
    """

    def __init__(self, session: object) -> None:
        self._session = session

    # Phase 3 TODO: implement all methods below

    async def top_objections(
        self, portfolio_id: str | None = None, limit: int = 10
    ) -> list[ObjectionSummary]:
        raise NotImplementedError("VideoAggregator.top_objections() — Phase 3")

    async def topic_trends(self, days: int = 30) -> list[TopicTrend]:
        raise NotImplementedError("VideoAggregator.topic_trends() — Phase 3")

    async def risk_summary(
        self, portfolio_id: str | None = None
    ) -> PortfolioRiskSummary:
        raise NotImplementedError("VideoAggregator.risk_summary() — Phase 3")
