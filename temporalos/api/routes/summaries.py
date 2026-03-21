"""Summaries API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...summarization.engine import get_summary_engine, SummaryType

router = APIRouter(prefix="/summaries", tags=["summaries"])


class SummaryRequest(BaseModel):
    summary_type: str = "executive"
    custom_template: str = ""


def _get_jobs() -> dict:
    from ...api.routes.process import _jobs  # type: ignore[attr-defined]
    return _jobs


@router.post("/{job_id}")
async def generate_summary(job_id: str, req: SummaryRequest) -> dict:
    """Generate a summary for a completed job."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.get("status") not in ("completed", "partial"):
        raise HTTPException(400, f"Job '{job_id}' is not yet completed")

    intel = job.get("intelligence")
    if not intel:
        raise HTTPException(400, "No intelligence data available for this job")

    try:
        summary_type = SummaryType(req.summary_type)
    except ValueError:
        valid = [t.value for t in SummaryType]
        raise HTTPException(400, f"Invalid summary_type '{req.summary_type}'. Valid: {valid}")

    engine = get_summary_engine()
    summary = engine.generate(intel, summary_type, req.custom_template)

    return {"job_id": job_id, "summary": summary.to_dict()}


@router.get("/{job_id}")
async def list_summaries(job_id: str) -> dict:
    """Return all cached summaries for a job."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    cached = job.get("summaries", {})
    return {"job_id": job_id, "summaries": cached, "available_types": [t.value for t in SummaryType]}


@router.get("/types/list")
async def list_summary_types() -> dict:
    """Return all available summary types."""
    return {"types": [t.value for t in SummaryType]}
