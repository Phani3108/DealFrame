"""Batch processing models."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BatchItem:
    item_id: str
    url: str
    status: BatchStatus = BatchStatus.PENDING
    job_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "url": self.url,
            "status": self.status.value,
            "job_id": self.job_id,
            "error": self.error,
        }


@dataclass
class BatchJob:
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    items: List[BatchItem] = field(default_factory=list)
    status: BatchStatus = BatchStatus.PENDING
    vertical: str = ""            # optional vertical pack
    schema_id: str = ""           # optional custom schema
    priority: int = 0             # higher = processed first
    created_at: float = field(default_factory=lambda: __import__("time").time())
    updated_at: float = field(default_factory=lambda: __import__("time").time())
    webhook_url: str = ""         # deliver result to this URL when done

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def completed_count(self) -> int:
        return sum(1 for i in self.items if i.status == BatchStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for i in self.items if i.status == BatchStatus.FAILED)

    @property
    def progress_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round((self.completed_count + self.failed_count) / self.total * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "total": self.total,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "progress_pct": self.progress_pct,
            "vertical": self.vertical,
            "schema_id": self.schema_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "items": [i.to_dict() for i in self.items],
        }
