"""Clips API routes."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...clips.extractor import ClipSpec, get_clip_extractor

router = APIRouter(prefix="/clips", tags=["clips"])


class ClipExtractRequest(BaseModel):
    label: str
    start_ms: int
    end_ms: int
    risk_score: float = 0.0
    topic: str = ""


def _get_jobs() -> dict:
    from ...api.routes.process import _jobs  # type: ignore[attr-defined]
    return _jobs


@router.get("/{job_id}")
async def list_clips(job_id: str) -> dict:
    """List all extracted clips for a job."""
    jobs = _get_jobs()
    if not jobs.get(job_id):
        raise HTTPException(404, f"Job '{job_id}' not found")
    extractor = get_clip_extractor()
    return {"job_id": job_id, "clips": extractor.list_clips(job_id)}


@router.post("/{job_id}/extract")
async def extract_clip(job_id: str, req: ClipExtractRequest) -> dict:
    """Extract a specific clip from a job's video."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.get("status") not in ("completed", "partial"):
        raise HTTPException(400, "Job not yet completed")

    video_path = job.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(400, "Video file not available for clipping")

    if req.end_ms <= req.start_ms:
        raise HTTPException(400, "end_ms must be greater than start_ms")

    spec = ClipSpec(
        label=req.label,
        start_ms=req.start_ms,
        end_ms=req.end_ms,
        risk_score=req.risk_score,
        topic=req.topic,
    )
    extractor = get_clip_extractor()
    try:
        clip = extractor.extract(video_path, job_id, spec)
    except RuntimeError as exc:
        raise HTTPException(500, f"Clip extraction failed: {exc}") from exc

    return {"job_id": job_id, "clip": clip.to_dict()}


@router.post("/{job_id}/significant")
async def extract_significant_clips(job_id: str, n: int = 5) -> dict:
    """Auto-extract the N most significant clips based on risk score."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    video_path = job.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(400, "Video file not available for clipping")

    intelligence = job.get("intelligence", {})
    segments = intelligence.get("segments", [])
    if not segments:
        raise HTTPException(400, "No segments available for this job")

    extractor = get_clip_extractor()
    specs = extractor.infer_significant_clips(segments, n=min(n, 10))
    clips = []
    for spec in specs:
        try:
            clip = extractor.extract(video_path, job_id, spec)
            clips.append(clip.to_dict())
        except RuntimeError:
            clips.append(spec.to_dict())

    return {"job_id": job_id, "clips": clips}


@router.get("/{job_id}/{clip_filename}")
async def serve_clip(job_id: str, clip_filename: str) -> FileResponse:
    """Download / stream a clip file."""
    from ...clips.extractor import CLIPS_DIR
    clip_path = CLIPS_DIR / job_id / clip_filename
    if not clip_path.exists():
        raise HTTPException(404, "Clip file not found")
    return FileResponse(str(clip_path), media_type="video/mp4",
                        filename=clip_filename)
