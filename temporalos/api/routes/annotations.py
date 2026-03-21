"""Annotation API routes — CRUD for collaborative transcript annotations."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/annotations", tags=["annotations"])


class CreateAnnotationRequest(BaseModel):
    job_id: str
    user_id: str = "default"
    segment_index: int
    start_word: int
    end_word: int
    label: str
    comment: str = ""
    tags: list[str] = []


class UpdateAnnotationRequest(BaseModel):
    label: Optional[str] = None
    comment: Optional[str] = None
    tags: Optional[list[str]] = None
    resolved: Optional[bool] = None


@router.get("")
async def list_annotations(
    job_id: str = Query(..., description="Job ID to list annotations for"),
    user_id: Optional[str] = Query(None),
) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    if user_id:
        anns = store.list_for_user(user_id)
    else:
        anns = store.list_for_job(job_id)
    return {"annotations": [a.to_dict() for a in anns], "total": len(anns)}


@router.post("")
async def create_annotation(req: CreateAnnotationRequest) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    try:
        ann = store.create(
            job_id=req.job_id, user_id=req.user_id,
            segment_index=req.segment_index,
            start_word=req.start_word, end_word=req.end_word,
            label=req.label, comment=req.comment, tags=req.tags,
        )
        return {"annotation": ann.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
async def annotation_summary(job_id: str = Query(...)) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    return {"job_id": job_id, "label_summary": store.label_summary(job_id), "total": store.count}


@router.get("/export")
async def export_training_data(job_id: str = Query(...)) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    return {"job_id": job_id, "training_data": store.export_training_data(job_id)}


@router.get("/{annotation_id}")
async def get_annotation(annotation_id: str) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    ann = store.get(annotation_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"annotation": ann.to_dict()}


@router.patch("/{annotation_id}")
async def update_annotation(annotation_id: str, req: UpdateAnnotationRequest) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        ann = store.update(annotation_id, **updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"annotation": ann.to_dict()}


@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    deleted = store.delete(annotation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"deleted": True}


@router.post("/{annotation_id}/resolve")
async def resolve_annotation(annotation_id: str) -> dict:
    from ...intelligence.annotations import get_annotation_store
    store = get_annotation_store()
    ann = store.resolve(annotation_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"annotation": ann.to_dict()}
