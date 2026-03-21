"""Diff Engine API routes — compare two video analysis jobs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/diff", tags=["diff"])


@router.get("/{job_a}/{job_b}")
async def compare_jobs(job_a: str, job_b: str) -> dict:
    """Compare two video analysis jobs side-by-side."""
    from ...intelligence.diff_engine import diff_calls
    from ...api.routes.process import _jobs

    a_data = _jobs.get(job_a)
    b_data = _jobs.get(job_b)
    if not a_data or not b_data:
        raise HTTPException(status_code=404, detail="One or both jobs not found")

    result_a = a_data.get("result", {})
    result_b = b_data.get("result", {})

    report = diff_calls(job_a, result_a, job_b, result_b)
    return {
        "job_a": job_a,
        "job_b": job_b,
        "report": report.to_dict(),
    }


@router.get("/jobs")
async def list_comparable_jobs() -> dict:
    """List completed jobs available for comparison."""
    from ...api.routes.process import _jobs
    completed = [
        {"job_id": jid, "status": jdata.get("status")}
        for jid, jdata in _jobs.items()
        if jdata.get("status") == "completed"
    ]
    return {"jobs": completed, "total": len(completed)}
