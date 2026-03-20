"""
Local pipeline API routes — Phase 5.

Exposes the local SLM pipeline over REST:
  POST /local/process          — process a video with zero API calls
  GET  /local/benchmark        — run local vs API benchmark on a video
  GET  /local/status           — check which models are available locally
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ...config import get_settings
from ...local.benchmark import BenchmarkRunner
from ...local.pipeline import LocalPipeline

router = APIRouter(prefix="/local", tags=["local"])

# In-memory job state (same pattern as observatory routes)
_local_jobs: dict[str, dict] = {}


def _run_local(jid: str, vpath: str, vision: bool) -> None:
    """Module-level background worker for local processing jobs."""
    from ...config import get_settings as _gs
    _settings = _gs()
    _local_jobs[jid]["status"] = "processing"
    try:
        pipeline = LocalPipeline(
            whisper_model=_settings.audio.whisper_model,
            adapter_path=_settings.finetuning.adapter_path,
            frame_interval_seconds=_settings.video.frame_interval_seconds,
            max_resolution=_settings.video.max_resolution,
        )
        result = pipeline.process(vpath, use_vision=vision)
        _local_jobs[jid].update({
            "status": "completed",
            "result": result.to_dict(),
            "extraction_model": result.extraction_model,
            "total_latency_ms": result.total_latency_ms,
        })
    except Exception as exc:
        _local_jobs[jid].update({"status": "failed", "error": str(exc)})


@router.get("/status")
async def local_status() -> dict:
    """Check which local models are available and ready."""
    settings = get_settings()

    # Check fine-tuned adapter
    adapter_path = settings.finetuning.adapter_path
    adapter_available = bool(adapter_path and Path(adapter_path).exists())

    # Check faster-whisper (used by default)
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        whisper_available = True
    except ImportError:
        whisper_available = False

    # Check Qwen VL
    try:
        from transformers import AutoProcessor  # noqa: F401
        qwen_available = True
    except ImportError:
        qwen_available = False

    return {
        "whisper_available": whisper_available,
        "whisper_model": settings.audio.whisper_model,
        "qwen_vl_available": qwen_available,
        "finetuned_adapter_available": adapter_available,
        "adapter_path": adapter_path or None,
        "active_extractor": "finetuned" if adapter_available else "rule_based",
        "cost_per_video_usd": 0.0,
    }


@router.post("/process", status_code=202)
async def local_process(
    background_tasks: BackgroundTasks,
    use_vision: bool = False,
    file: UploadFile = File(...),
) -> dict:
    """
    Process a video using the fully local pipeline (no external API calls).
    Returns a job_id to poll via GET /local/process/{job_id}.
    """
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    if suffix not in settings.video.supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Supported: {settings.video.supported_formats}",
        )

    job_id = str(uuid.uuid4())
    upload_dir = Path(settings.app.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(upload_dir / f"local_{job_id}.{suffix}")

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _local_jobs[job_id] = {"status": "pending"}
    background_tasks.add_task(_run_local, job_id, video_path, use_vision)
    return {"job_id": job_id, "status": "pending"}


@router.get("/process/{job_id}")
async def get_local_job(job_id: str) -> dict:
    """Get the status and result of a local processing job."""
    job = _local_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, **job}


@router.get("/jobs")
async def list_local_jobs() -> dict:
    """List all local processing jobs."""
    return {
        "jobs": [
            {"job_id": jid, "status": j["status"]}
            for jid, j in _local_jobs.items()
        ],
        "total": len(_local_jobs),
    }


@router.post("/benchmark")
async def run_benchmark(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict:
    """
    Run a local vs rule-based benchmark on the uploaded video.
    Compares local pipeline latency against a pure timing baseline.
    Returns a job_id to poll.
    """
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    if suffix not in settings.video.supported_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{suffix}'")

    job_id = f"bench_{uuid.uuid4()}"
    upload_dir = Path(settings.app.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(upload_dir / f"{job_id}.{suffix}")

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _local_jobs[job_id] = {"status": "pending"}

    def _run_bench(jid: str, vpath: str) -> None:
        _local_jobs[jid]["status"] = "running"
        try:
            runner = BenchmarkRunner()
            pipeline = LocalPipeline(
                whisper_model=settings.audio.whisper_model,
                adapter_path=settings.finetuning.adapter_path,
            )
            local_result = runner.run_local(vpath, pipeline)

            # Simple stub "API" baseline that just times without real API calls
            from ...extraction.models.finetuned import FineTunedExtractionModel
            stub_model = FineTunedExtractionModel(adapter_path="")
            api_result = runner.run_api(vpath, stub_model)

            comparison = runner.compare(local_result, api_result)
            _local_jobs[jid].update({
                "status": "completed",
                "comparison": comparison.to_dict(),
            })
        except Exception as exc:
            _local_jobs[jid].update({"status": "failed", "error": str(exc)})

    background_tasks.add_task(_run_bench, job_id, video_path)
    return {"job_id": job_id, "status": "pending"}
