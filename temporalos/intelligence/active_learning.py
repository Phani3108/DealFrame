"""Confidence-Gated Active Learning — route low-confidence extractions to human review.

Features:
- Confidence threshold gating
- Review queue with priority ordering
- Reviewed items feed back into training data
- Metrics on review throughput and label distribution
- DB persistence via optional session_factory
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"


@dataclass
class ReviewItem:
    id: str
    job_id: str
    segment_index: int
    extraction: Dict[str, Any]
    confidence: float
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: Optional[str] = None
    corrected_extraction: Optional[Dict[str, Any]] = None
    review_notes: str = ""
    created_at: float = 0.0
    reviewed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "job_id": self.job_id,
            "segment_index": self.segment_index,
            "extraction": self.extraction,
            "confidence": self.confidence,
            "status": self.status.value,
            "created_at": self.created_at,
        }
        if self.reviewer:
            d["reviewer"] = self.reviewer
            d["reviewed_at"] = self.reviewed_at
        if self.corrected_extraction:
            d["corrected_extraction"] = self.corrected_extraction
        if self.review_notes:
            d["review_notes"] = self.review_notes
        return d


class ActiveLearningQueue:
    """Manages the human review queue with confidence gating and optional DB persistence."""

    def __init__(self, confidence_threshold: float = 0.6,
                 session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> None:
        self.threshold = confidence_threshold
        self._items: Dict[str, ReviewItem] = {}
        self._sf = session_factory

    def gate(self, job_id: str, segment_index: int,
             extraction: Dict[str, Any], confidence: float) -> Optional[ReviewItem]:
        """Gate an extraction — if below threshold, add to review queue.
        Returns ReviewItem if queued, None if confidence is sufficient."""
        if confidence >= self.threshold:
            return None
        item = ReviewItem(
            id=uuid.uuid4().hex[:12],
            job_id=job_id,
            segment_index=segment_index,
            extraction=extraction,
            confidence=confidence,
            created_at=time.time(),
        )
        self._items[item.id] = item
        return item

    def get_queue(self, status: Optional[ReviewStatus] = None,
                  limit: int = 50) -> List[ReviewItem]:
        """Get review items, optionally filtered by status. Lowest confidence first."""
        items = list(self._items.values())
        if status:
            items = [i for i in items if i.status == status]
        items.sort(key=lambda i: i.confidence)
        return items[:limit]

    def claim(self, item_id: str, reviewer: str) -> Optional[ReviewItem]:
        """Claim an item for review."""
        item = self._items.get(item_id)
        if not item or item.status != ReviewStatus.PENDING:
            return None
        item.status = ReviewStatus.IN_REVIEW
        item.reviewer = reviewer
        return item

    def approve(self, item_id: str, reviewer: str,
                notes: str = "") -> Optional[ReviewItem]:
        """Approve an extraction as correct."""
        item = self._items.get(item_id)
        if not item:
            return None
        item.status = ReviewStatus.APPROVED
        item.reviewer = reviewer
        item.review_notes = notes
        item.reviewed_at = time.time()
        return item

    def correct(self, item_id: str, reviewer: str,
                corrected: Dict[str, Any], notes: str = "") -> Optional[ReviewItem]:
        """Submit a corrected extraction."""
        item = self._items.get(item_id)
        if not item:
            return None
        item.status = ReviewStatus.CORRECTED
        item.reviewer = reviewer
        item.corrected_extraction = corrected
        item.review_notes = notes
        item.reviewed_at = time.time()
        return item

    def reject(self, item_id: str, reviewer: str,
               notes: str = "") -> Optional[ReviewItem]:
        """Reject an extraction (garbage / irrelevant)."""
        item = self._items.get(item_id)
        if not item:
            return None
        item.status = ReviewStatus.REJECTED
        item.reviewer = reviewer
        item.review_notes = notes
        item.reviewed_at = time.time()
        return item

    def export_training_data(self) -> List[Dict[str, Any]]:
        """Export reviewed items as training data.
        Approved items use original extraction, corrected items use corrected version."""
        data: List[Dict[str, Any]] = []
        for item in self._items.values():
            if item.status == ReviewStatus.APPROVED:
                data.append({
                    "job_id": item.job_id,
                    "segment_index": item.segment_index,
                    "extraction": item.extraction,
                    "source": "human_approved",
                })
            elif item.status == ReviewStatus.CORRECTED and item.corrected_extraction:
                data.append({
                    "job_id": item.job_id,
                    "segment_index": item.segment_index,
                    "extraction": item.corrected_extraction,
                    "source": "human_corrected",
                })
        return data

    def metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        status_counts: Dict[str, int] = {}
        total_confidence = 0.0
        for item in self._items.values():
            status_counts[item.status.value] = status_counts.get(item.status.value, 0) + 1
            total_confidence += item.confidence
        count = len(self._items)
        return {
            "total_items": count,
            "status_counts": status_counts,
            "avg_confidence": round(total_confidence / max(count, 1), 3),
            "threshold": self.threshold,
            "training_data_count": len(self.export_training_data()),
        }

    @property
    def pending_count(self) -> int:
        return sum(1 for i in self._items.values() if i.status == ReviewStatus.PENDING)

    # ── Async DB-backed methods ───────────────────────────────────────────────

    async def _persist_item(self, item: ReviewItem) -> None:
        """Persist a review item to DB (upsert)."""
        if not self._sf:
            return
        from ..db.models import ReviewItemRecord
        async with self._sf() as session:
            row = (await session.execute(
                select(ReviewItemRecord).where(ReviewItemRecord.uid == item.id)
            )).scalar_one_or_none()
            if row:
                row.status = item.status.value
                row.reviewer = item.reviewer
                row.corrected_extraction = item.corrected_extraction
                row.review_notes = item.review_notes
                if item.reviewed_at:
                    row.reviewed_at = datetime.fromtimestamp(item.reviewed_at, tz=timezone.utc)
            else:
                session.add(ReviewItemRecord(
                    uid=item.id, job_id=item.job_id,
                    segment_index=item.segment_index,
                    extraction=item.extraction,
                    confidence=item.confidence,
                    status=item.status.value,
                    reviewer=item.reviewer,
                    corrected_extraction=item.corrected_extraction,
                    review_notes=item.review_notes,
                    created_at=datetime.fromtimestamp(item.created_at, tz=timezone.utc) if item.created_at else None,
                    reviewed_at=datetime.fromtimestamp(item.reviewed_at, tz=timezone.utc) if item.reviewed_at else None,
                ))
            await session.commit()

    async def async_gate(self, job_id: str, segment_index: int,
                         extraction: Dict[str, Any], confidence: float) -> Optional[ReviewItem]:
        """Gate with DB persistence."""
        item = self.gate(job_id, segment_index, extraction, confidence)
        if item:
            await self._persist_item(item)
        return item

    async def async_approve(self, item_id: str, reviewer: str,
                            notes: str = "") -> Optional[ReviewItem]:
        item = self.approve(item_id, reviewer, notes)
        if item:
            await self._persist_item(item)
        return item

    async def async_correct(self, item_id: str, reviewer: str,
                            corrected: Dict[str, Any], notes: str = "") -> Optional[ReviewItem]:
        item = self.correct(item_id, reviewer, corrected, notes)
        if item:
            await self._persist_item(item)
        return item

    async def async_reject(self, item_id: str, reviewer: str,
                           notes: str = "") -> Optional[ReviewItem]:
        item = self.reject(item_id, reviewer, notes)
        if item:
            await self._persist_item(item)
        return item

    async def load_from_db(self) -> None:
        """Populate in-memory from DB at startup."""
        if not self._sf:
            return
        from ..db.models import ReviewItemRecord
        async with self._sf() as session:
            rows = (await session.execute(select(ReviewItemRecord))).scalars().all()
            for r in rows:
                item = ReviewItem(
                    id=r.uid, job_id=r.job_id,
                    segment_index=r.segment_index,
                    extraction=r.extraction or {},
                    confidence=r.confidence,
                    status=ReviewStatus(r.status) if r.status else ReviewStatus.PENDING,
                    reviewer=r.reviewer,
                    corrected_extraction=r.corrected_extraction,
                    review_notes=r.review_notes or "",
                    created_at=r.created_at.timestamp() if r.created_at else 0,
                    reviewed_at=r.reviewed_at.timestamp() if r.reviewed_at else 0,
                )
                self._items[item.id] = item


_queue: Optional[ActiveLearningQueue] = None


def get_active_learning_queue(threshold: float = 0.6) -> ActiveLearningQueue:
    global _queue
    if _queue is None:
        _queue = ActiveLearningQueue(threshold)
    return _queue


def init_active_learning_queue(threshold: float = 0.6,
                               session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> ActiveLearningQueue:
    """Initialize with DB persistence. Call once at startup."""
    global _queue
    _queue = ActiveLearningQueue(confidence_threshold=threshold, session_factory=session_factory)
    return _queue


def set_active_learning_queue(q: ActiveLearningQueue) -> None:
    global _queue
    _queue = q
