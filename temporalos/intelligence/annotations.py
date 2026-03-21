"""Collaborative Annotations — team members annotate transcript segments.

Features:
- Highlight transcript ranges with comments and labels
- Labels feed into fine-tuning training data
- CRUD operations on annotations
- Label aggregation for active learning
- DB persistence via optional session_factory
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class Annotation:
    id: str
    job_id: str
    user_id: str
    segment_index: int
    start_word: int
    end_word: int
    label: str  # objection | decision_signal | risk | positive | question | action_item | custom
    comment: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    tags: List[str] = field(default_factory=list)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "segment_index": self.segment_index,
            "start_word": self.start_word,
            "end_word": self.end_word,
            "label": self.label,
            "comment": self.comment,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "resolved": self.resolved,
        }


class AnnotationStore:
    """Annotation store with optional DB persistence."""

    VALID_LABELS = {
        "objection", "decision_signal", "risk", "positive",
        "question", "action_item", "custom",
    }

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> None:
        self._annotations: Dict[str, Annotation] = {}
        self._sf = session_factory

    def create(self, job_id: str, user_id: str, segment_index: int,
               start_word: int, end_word: int, label: str,
               comment: str = "", tags: Optional[List[str]] = None) -> Annotation:
        if label not in self.VALID_LABELS:
            raise ValueError(f"Invalid label: {label}. Must be one of {self.VALID_LABELS}")
        now = time.time()
        ann = Annotation(
            id=uuid.uuid4().hex[:12],
            job_id=job_id,
            user_id=user_id,
            segment_index=segment_index,
            start_word=start_word,
            end_word=end_word,
            label=label,
            comment=comment,
            created_at=now,
            updated_at=now,
            tags=tags or [],
        )
        self._annotations[ann.id] = ann
        return ann

    def get(self, annotation_id: str) -> Optional[Annotation]:
        return self._annotations.get(annotation_id)

    def update(self, annotation_id: str, **kwargs: Any) -> Optional[Annotation]:
        ann = self._annotations.get(annotation_id)
        if not ann:
            return None
        for key, val in kwargs.items():
            if key == "label" and val not in self.VALID_LABELS:
                raise ValueError(f"Invalid label: {val}")
            if hasattr(ann, key) and key not in ("id", "job_id", "created_at"):
                setattr(ann, key, val)
        ann.updated_at = time.time()
        return ann

    def delete(self, annotation_id: str) -> bool:
        return self._annotations.pop(annotation_id, None) is not None

    def list_for_job(self, job_id: str) -> List[Annotation]:
        return sorted(
            [a for a in self._annotations.values() if a.job_id == job_id],
            key=lambda a: (a.segment_index, a.start_word),
        )

    def list_for_user(self, user_id: str) -> List[Annotation]:
        return [a for a in self._annotations.values() if a.user_id == user_id]

    def label_summary(self, job_id: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for a in self._annotations.values():
            if a.job_id == job_id:
                counts[a.label] = counts.get(a.label, 0) + 1
        return counts

    def export_training_data(self, job_id: str) -> List[Dict[str, Any]]:
        """Export annotations as training data for fine-tuning."""
        rows: List[Dict[str, Any]] = []
        for a in self.list_for_job(job_id):
            rows.append({
                "job_id": a.job_id,
                "segment_index": a.segment_index,
                "start_word": a.start_word,
                "end_word": a.end_word,
                "label": a.label,
                "comment": a.comment,
                "tags": a.tags,
                "annotator": a.user_id,
            })
        return rows

    def resolve(self, annotation_id: str) -> Optional[Annotation]:
        return self.update(annotation_id, resolved=True)

    @property
    def count(self) -> int:
        return len(self._annotations)

    # ── Async DB-backed methods ───────────────────────────────────────────────

    async def async_create(self, job_id: str, user_id: str, segment_index: int,
                           start_word: int, end_word: int, label: str,
                           comment: str = "", tags: Optional[List[str]] = None) -> Annotation:
        """Create with DB persistence."""
        ann = self.create(job_id, user_id, segment_index, start_word, end_word,
                          label, comment, tags)
        if self._sf:
            from ..db.models import AnnotationRecord
            async with self._sf() as session:
                record = AnnotationRecord(
                    uid=ann.id, job_id=ann.job_id, user_id=ann.user_id,
                    segment_index=ann.segment_index, start_word=ann.start_word,
                    end_word=ann.end_word, label=ann.label, comment=ann.comment,
                    tags=ann.tags, resolved=ann.resolved,
                    created_at=datetime.fromtimestamp(ann.created_at, tz=timezone.utc),
                    updated_at=datetime.fromtimestamp(ann.updated_at, tz=timezone.utc),
                )
                session.add(record)
                await session.commit()
        return ann

    async def async_update(self, annotation_id: str, **kwargs: Any) -> Optional[Annotation]:
        """Update with DB persistence."""
        ann = self.update(annotation_id, **kwargs)
        if ann and self._sf:
            from ..db.models import AnnotationRecord
            async with self._sf() as session:
                row = (await session.execute(
                    select(AnnotationRecord).where(AnnotationRecord.uid == annotation_id)
                )).scalar_one_or_none()
                if row:
                    for key, val in kwargs.items():
                        if hasattr(row, key) and key not in ("id", "uid", "job_id", "created_at"):
                            setattr(row, key, val)
                    row.updated_at = datetime.now(timezone.utc)
                    await session.commit()
        return ann

    async def async_delete(self, annotation_id: str) -> bool:
        """Delete with DB persistence."""
        result = self.delete(annotation_id)
        if result and self._sf:
            from ..db.models import AnnotationRecord
            async with self._sf() as session:
                await session.execute(
                    delete(AnnotationRecord).where(AnnotationRecord.uid == annotation_id)
                )
                await session.commit()
        return result

    async def load_from_db(self) -> None:
        """Populate in-memory from DB at startup."""
        if not self._sf:
            return
        from ..db.models import AnnotationRecord
        async with self._sf() as session:
            rows = (await session.execute(select(AnnotationRecord))).scalars().all()
            for r in rows:
                ann = Annotation(
                    id=r.uid, job_id=r.job_id, user_id=r.user_id,
                    segment_index=r.segment_index, start_word=r.start_word,
                    end_word=r.end_word, label=r.label, comment=r.comment or "",
                    created_at=r.created_at.timestamp() if r.created_at else 0,
                    updated_at=r.updated_at.timestamp() if r.updated_at else 0,
                    tags=r.tags if isinstance(r.tags, list) else [],
                    resolved=r.resolved or False,
                )
                self._annotations[ann.id] = ann


_store: Optional[AnnotationStore] = None


def get_annotation_store() -> AnnotationStore:
    global _store
    if _store is None:
        _store = AnnotationStore()
    return _store


def init_annotation_store(session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> AnnotationStore:
    """Initialize with DB persistence. Call once at startup."""
    global _store
    _store = AnnotationStore(session_factory=session_factory)
    return _store


def set_annotation_store(store: AnnotationStore) -> None:
    global _store
    _store = store
