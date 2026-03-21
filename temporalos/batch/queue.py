"""Batch queue — in-process priority queue with Celery-ready interface.

Drop-in replacement: swap BatchQueue with a Celery chord/group when
you need distributed processing.
"""
from __future__ import annotations

import asyncio
import heapq
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional

from temporalos.batch.models import BatchItem, BatchJob, BatchStatus

logger = logging.getLogger(__name__)


class BatchQueue:
    """In-memory priority max-heap of BatchJob objects.

    Thread-/async-safe via asyncio.Lock — use from a single event loop.
    """

    def __init__(self) -> None:
        self._heap: List[tuple] = []   # (-priority, created_at, batch_id)
        self._jobs: Dict[str, BatchJob] = {}
        self._lock = asyncio.Lock()

    async def submit(self, job: BatchJob) -> str:
        async with self._lock:
            self._jobs[job.batch_id] = job
            heapq.heappush(self._heap, (-job.priority, job.created_at, job.batch_id))
            logger.info("Batch %s queued (%d items)", job.batch_id, job.total)
        return job.batch_id

    async def pop_next(self) -> Optional[BatchJob]:
        async with self._lock:
            while self._heap:
                _, _, bid = heapq.heappop(self._heap)
                job = self._jobs.get(bid)
                if job and job.status == BatchStatus.PENDING:
                    return job
        return None

    def get(self, batch_id: str) -> Optional[BatchJob]:
        return self._jobs.get(batch_id)

    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        jobs = sorted(self._jobs.values(), key=lambda j: -j.created_at)
        return jobs[:limit]

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status == BatchStatus.PENDING)


_queue: Optional[BatchQueue] = None


def get_batch_queue() -> BatchQueue:
    global _queue
    if _queue is None:
        _queue = BatchQueue()
    return _queue
