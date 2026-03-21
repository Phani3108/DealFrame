"""Active Learning API routes — review queue, approve/correct/reject."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/active-learning", tags=["active-learning"])


class GateRequest(BaseModel):
    job_id: str
    segment_index: int
    extraction: dict
    confidence: float


class ReviewRequest(BaseModel):
    reviewer: str = "default"
    notes: str = ""
    corrected_extraction: Optional[dict] = None


@router.get("/queue")
async def get_queue(
    status: Optional[str] = Query(None, description="Filter by status: pending|in_review|approved|corrected|rejected"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue, ReviewStatus
    q = get_active_learning_queue()
    rs = ReviewStatus(status) if status else None
    items = q.get_queue(status=rs, limit=limit)
    return {"items": [i.to_dict() for i in items], "total": len(items)}


@router.get("/metrics")
async def get_metrics() -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    return q.metrics()


@router.get("/export")
async def export_training() -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    return {"training_data": q.export_training_data(), "count": len(q.export_training_data())}


@router.post("/gate")
async def gate_extraction(req: GateRequest) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    item = q.gate(req.job_id, req.segment_index, req.extraction, req.confidence)
    if item:
        return {"queued": True, "item": item.to_dict()}
    return {"queued": False, "message": "Confidence above threshold"}


@router.post("/{item_id}/claim")
async def claim_item(item_id: str, reviewer: str = Query("default")) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    item = q.claim(item_id, reviewer)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found or not pending")
    return {"item": item.to_dict()}


@router.post("/{item_id}/approve")
async def approve_item(item_id: str, req: ReviewRequest) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    item = q.approve(item_id, req.reviewer, req.notes)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": item.to_dict()}


@router.post("/{item_id}/correct")
async def correct_item(item_id: str, req: ReviewRequest) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    if not req.corrected_extraction:
        raise HTTPException(status_code=400, detail="corrected_extraction required")
    item = q.correct(item_id, req.reviewer, req.corrected_extraction, req.notes)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": item.to_dict()}


@router.post("/{item_id}/reject")
async def reject_item(item_id: str, req: ReviewRequest) -> dict:
    from ...intelligence.active_learning import get_active_learning_queue
    q = get_active_learning_queue()
    item = q.reject(item_id, req.reviewer, req.notes)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": item.to_dict()}
