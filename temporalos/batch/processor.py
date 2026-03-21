"""Batch processor — async worker that drains the BatchQueue.

Calls the standard pipeline (process_video_file path) for each item
and updates item status in-place.  Fires the batch webhook when done.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from temporalos.batch.models import BatchItem, BatchJob, BatchStatus
from temporalos.batch.queue import BatchQueue, get_batch_queue

logger = logging.getLogger(__name__)


ProcessFn = Callable[[str, str, Dict[str, Any]], Any]   # (url, job_id, opts) → intel


class BatchProcessor:
    """Asyncio-based processor that reads jobs from BatchQueue.

    Inject `process_fn` to call the real pipeline; defaults to a
    no-op stub (useful for testing).
    """

    def __init__(
        self,
        queue: Optional[BatchQueue] = None,
        process_fn: Optional[ProcessFn] = None,
        concurrency: int = 2,
    ) -> None:
        self.queue = queue or get_batch_queue()
        self._process_fn = process_fn or _noop_process
        self.concurrency = concurrency
        self._running = False

    async def _process_item(self, item: BatchItem, job: BatchJob) -> None:
        item.status = BatchStatus.RUNNING
        job.updated_at = time.time()
        try:
            opts: Dict[str, Any] = {"vertical": job.vertical, "schema_id": job.schema_id}
            result = await asyncio.to_thread(self._process_fn, item.url, item.item_id, opts)
            item.job_id = result.get("job_id") if isinstance(result, dict) else item.item_id
            item.status = BatchStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch item %s failed: %s", item.item_id, exc)
            item.status = BatchStatus.FAILED
            item.error = str(exc)[:200]
        job.updated_at = time.time()

    async def _run_job(self, job: BatchJob) -> None:
        job.status = BatchStatus.RUNNING
        job.updated_at = time.time()
        sem = asyncio.Semaphore(self.concurrency)

        async def guarded(item: BatchItem) -> None:
            async with sem:
                await self._process_item(item, job)

        await asyncio.gather(*[guarded(item) for item in job.items])

        job.status = (
            BatchStatus.COMPLETED if job.failed_count == 0
            else BatchStatus.PARTIAL if job.completed_count > 0
            else BatchStatus.FAILED
        )
        job.updated_at = time.time()
        logger.info(
            "Batch %s done: %d/%d completed, %d failed",
            job.batch_id, job.completed_count, job.total, job.failed_count,
        )

        # Optionally fire webhook
        if job.webhook_url:
            try:
                from temporalos.integrations.base import http_post
                http_post(job.webhook_url, job.to_dict(), {})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Batch webhook failed for %s: %s", job.batch_id, exc)

    async def run_once(self) -> Optional[BatchJob]:
        """Process the next job from the queue. Returns the job or None."""
        job = await self.queue.pop_next()
        if job is None:
            return None
        await self._run_job(job)
        return job

    async def run_forever(self, poll_interval: float = 1.0) -> None:
        """Continuously drain the queue. Run in a background task."""
        self._running = True
        logger.info("BatchProcessor started (concurrency=%d)", self.concurrency)
        while self._running:
            job = await self.queue.pop_next()
            if job is None:
                await asyncio.sleep(poll_interval)
                continue
            await self._run_job(job)

    def stop(self) -> None:
        self._running = False


def _noop_process(url: str, item_id: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    """Stub process function — returns a fake job_id immediately."""
    return {"job_id": uuid.uuid4().hex, "url": url, "status": "completed"}


_processor: Optional[BatchProcessor] = None


def get_batch_processor(process_fn: Optional[ProcessFn] = None) -> BatchProcessor:
    global _processor
    if _processor is None:
        _processor = BatchProcessor(process_fn=process_fn)
    return _processor
