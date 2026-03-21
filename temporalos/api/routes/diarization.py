"""Diarization API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...diarization.diarizer import get_diarizer, DiarizationSegment
from ...diarization.speaker_intel import compute_speaker_intelligence

router = APIRouter(prefix="/diarization", tags=["diarization"])

# Shared job store reference — routes that need job data import _jobs lazily
def _get_jobs() -> dict:
    from ...api.routes.process import _jobs  # type: ignore[attr-defined]
    return _jobs


@router.get("/{job_id}/speakers")
async def get_speaker_intelligence(job_id: str) -> dict:
    """Return per-speaker analytics for a completed job."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.get("status") not in ("completed", "partial"):
        raise HTTPException(400, f"Job '{job_id}' is not yet completed (status={job.get('status')})")

    # Prefer pre-computed speaker_intelligence stored during processing
    si = job.get("speaker_intelligence")
    if si:
        return {"job_id": job_id, "speaker_intelligence": si}

    # Fall back: recompute from aligned words
    words = job.get("words", [])
    if not words:
        return {"job_id": job_id, "speaker_intelligence": None, "note": "No word-level data available"}

    diarizer = get_diarizer()
    labeled_words = diarizer.diarize(words)
    intel = compute_speaker_intelligence(labeled_words)
    segments = diarizer.get_segments(labeled_words)

    return {
        "job_id": job_id,
        "speaker_intelligence": intel.to_dict(),
        "segments": [s.to_dict() for s in segments],
    }


@router.get("/{job_id}/segments")
async def get_diarization_segments(job_id: str) -> dict:
    """Return raw diarization segment boundaries."""
    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    words = job.get("words", [])
    if not words:
        return {"job_id": job_id, "segments": []}

    diarizer = get_diarizer()
    labeled = diarizer.diarize(words)
    segments = diarizer.get_segments(labeled)
    return {"job_id": job_id, "segments": [s.to_dict() for s in segments]}
