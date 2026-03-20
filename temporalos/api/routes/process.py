"""Process route — submit a video for analysis, poll for results."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ...alignment.aligner import align
from ...audio.whisper import transcribe
from ...config import get_settings
from ...extraction.models.gpt4o import GPT4oExtractionModel
from ...ingestion.extractor import extract_frames, get_video_duration_ms
from ...observability.telemetry import get_tracer

router = APIRouter(tags=["process"])

# Simple in-memory job store for Phase 1.
# Phase 3 will migrate this to the PostgreSQL DB with a proper jobs table.
_jobs: dict[str, dict] = {}


# ── Pipeline (runs in FastAPI's background thread-pool) ────────────────────────

def _run_pipeline(job_id: str, video_path: str, frames_dir: str) -> None:
    """
    Synchronous pipeline runner.
    FastAPI automatically runs sync background tasks in a thread-pool executor.
    """
    tracer = get_tracer()
    settings = get_settings()

    with tracer.start_as_current_span("pipeline.run") as span:
        span.set_attribute("pipeline.job_id", job_id)

        try:
            _jobs[job_id]["status"] = "processing"

            # ── Stage 1: Frame extraction ──────────────────────────────────
            frames = extract_frames(
                video_path=video_path,
                output_dir=frames_dir,
                interval_seconds=settings.video.frame_interval_seconds,
                max_resolution=settings.video.max_resolution,
            )
            _jobs[job_id]["stages_done"].append("frame_extraction")
            span.set_attribute("pipeline.frame_count", len(frames))

            # ── Stage 2: Transcription ─────────────────────────────────────
            language = (
                settings.audio.language
                if settings.audio.language != "auto"
                else None
            )
            words = transcribe(
                video_path=video_path,
                model_name=settings.audio.whisper_model,
                language=language,
            )
            _jobs[job_id]["stages_done"].append("transcription")
            span.set_attribute("pipeline.word_count", len(words))

            # ── Stage 3: Temporal alignment ────────────────────────────────
            segments = align(frames, words)
            _jobs[job_id]["stages_done"].append("alignment")

            # ── Stage 4: Structured extraction ────────────────────────────
            extractor = GPT4oExtractionModel.from_settings()
            min_words = settings.extraction.min_words_per_segment
            results: list[dict] = []

            for seg in segments:
                if len(seg.words) < min_words:
                    continue
                ext = extractor.extract(seg)
                results.append({"timestamp": seg.timestamp_str, **ext.to_dict()})

            _jobs[job_id]["stages_done"].append("extraction")

            overall_risk = (
                round(sum(r["risk_score"] for r in results) / len(results), 2)
                if results
                else 0.0
            )

            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = {
                "segments": results,
                "overall_risk_score": overall_risk,
                "segment_count": len(results),
            }
            span.set_attribute("pipeline.segments_extracted", len(results))

        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            span.record_exception(exc)
            span.set_attribute("pipeline.error", str(exc))


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/process", status_code=202)
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    """
    Submit a video file for processing.
    Returns a job_id immediately; poll GET /jobs/{job_id} for results.
    """
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    if suffix not in settings.video.supported_formats:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported format '{suffix}'. "
                f"Supported: {settings.video.supported_formats}"
            ),
        )

    job_id = str(uuid.uuid4())
    upload_dir = Path(settings.app.upload_dir)
    frames_dir = str(Path(settings.app.frames_dir) / job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(upload_dir / f"{job_id}.{suffix}")

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _jobs[job_id] = {"status": "pending", "stages_done": []}
    background_tasks.add_task(_run_pipeline, job_id, video_path, frames_dir)

    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """Poll pipeline progress and retrieve results when completed."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@router.get("/jobs")
async def list_jobs() -> dict:
    """List all jobs and their statuses (dev convenience endpoint)."""
    summary = {
        jid: {"status": j["status"], "stages_done": j.get("stages_done", [])}
        for jid, j in _jobs.items()
    }
    return {"jobs": summary, "total": len(_jobs)}
