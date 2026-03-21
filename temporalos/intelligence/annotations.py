"""Collaborative Annotations — team members annotate transcript segments.

Features:
- Highlight transcript ranges with comments and labels
- Labels feed into fine-tuning training data
- CRUD operations on annotations
- Label aggregation for active learning
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    """In-memory annotation store with CRUD."""

    VALID_LABELS = {
        "objection", "decision_signal", "risk", "positive",
        "question", "action_item", "custom",
    }

    def __init__(self) -> None:
        self._annotations: Dict[str, Annotation] = {}

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


_store: Optional[AnnotationStore] = None


def get_annotation_store() -> AnnotationStore:
    global _store
    if _store is None:
        _store = AnnotationStore()
    return _store


def set_annotation_store(store: AnnotationStore) -> None:
    global _store
    _store = store
