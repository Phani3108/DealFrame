"""Batch processing API routes."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ...batch.models import BatchItem, BatchJob, BatchStatus
from ...batch.queue import get_batch_queue
from ...batch.processor import get_batch_processor

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchSubmitRequest(BaseModel):
    urls: List[str]
    vertical: str = ""
    schema_id: str = ""
    priority: int = 0
    webhook_url: str = ""


@router.post("")
async def submit_batch(req: BatchSubmitRequest, background: BackgroundTasks) -> dict:
    """Submit a batch of video URLs for processing."""
    if not req.urls:
        raise HTTPException(400, "At least one URL required")
    if len(req.urls) > 500:
        raise HTTPException(400, "Maximum 500 URLs per batch")

    items = [
        BatchItem(item_id=uuid.uuid4().hex, url=url)
        for url in req.urls
    ]
    job = BatchJob(
        items=items,
        vertical=req.vertical,
        schema_id=req.schema_id,
        priority=req.priority,
        webhook_url=req.webhook_url,
    )

    queue = get_batch_queue()
    batch_id = await queue.submit(job)

    # Start the processor in background
    background.add_task(_run_batch, batch_id)

    return {
        "batch_id": batch_id,
        "total": len(items),
        "status": BatchStatus.PENDING.value,
    }


@router.get("/{batch_id}")
async def get_batch_status(batch_id: str) -> dict:
    queue = get_batch_queue()
    job = queue.get(batch_id)
    if not job:
        raise HTTPException(404, f"Batch '{batch_id}' not found")
    return job.to_dict()


@router.get("")
async def list_batches(limit: int = 20) -> dict:
    queue = get_batch_queue()
    jobs = queue.list_jobs(limit=limit)
    pending = queue.pending_count()
    return {
        "batches": [j.to_dict() for j in jobs],
        "total": len(jobs),
        "pending": pending,
    }


@router.delete("/{batch_id}/cancel")
async def cancel_batch(batch_id: str) -> dict:
    """Mark a pending batch as cancelled (sets status → failed)."""
    queue = get_batch_queue()
    job = queue.get(batch_id)
    if not job:
        raise HTTPException(404, f"Batch '{batch_id}' not found")
    if job.status != BatchStatus.PENDING:
        raise HTTPException(400, f"Cannot cancel a batch in status '{job.status.value}'")
    job.status = BatchStatus.FAILED
    for item in job.items:
        if item.status == BatchStatus.PENDING:
            item.status = BatchStatus.FAILED
            item.error = "Batch cancelled by user"
    return {"cancelled": True, "batch_id": batch_id}


async def _run_batch(batch_id: str) -> None:
    """Background task: process a batch job."""
    queue = get_batch_queue()
    job = queue.get(batch_id)
    if not job:
        return
    processor = get_batch_processor()
    await processor._run_job(job)
