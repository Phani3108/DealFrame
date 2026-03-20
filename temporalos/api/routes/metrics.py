"""Observability API routes: Prometheus metrics, drift, calibration, review queue."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ...observability.calibration import ConfidenceCalibrator
from ...observability.drift_detector import get_drift_detector
from ...observability.metrics import get_metrics

router = APIRouter(tags=["observability"])

# Module-level calibrator shared across requests (singleton per process)
_calibrator = ConfidenceCalibrator()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus-format metrics scrape endpoint (for Grafana Agent / Prometheus)."""
    metrics = get_metrics()
    body, content_type = metrics.render_prometheus()
    return Response(content=body, media_type=content_type)


@router.get("/observability/drift")
async def drift_report() -> dict:
    """Current drift detection report comparing recent extractions to baseline."""
    detector = get_drift_detector()
    report = detector.check_drift()
    return {
        "total_recorded": detector.total_recorded,
        "baseline_frozen": detector.baseline_frozen,
        **report.to_dict(),
    }


@router.get("/observability/calibration")
async def calibration_report() -> dict:
    """Confidence calibration report — ECE and per-bin reliability breakdown."""
    report = _calibrator.compute()
    return report.to_dict()


@router.post("/observability/calibration/sample")
async def add_calibration_sample(confidence: float, correct: bool) -> dict:
    """Add a (confidence, correct) sample for ongoing calibration tracking."""
    if not 0.0 <= confidence <= 1.0:
        raise HTTPException(status_code=422, detail="confidence must be in [0.0, 1.0]")
    _calibrator.add_sample(confidence=confidence, correct=correct)
    return {"sample_count": _calibrator.sample_count}


@router.get("/review/queue")
async def review_queue(limit: int = 20, max_confidence: float = 0.5) -> dict:
    """
    Returns low-confidence extraction records queued for human review.
    In production this queries the DB; here it surfaces drift status alongside
    the (empty) queue so dashboards always have current health context.
    """
    detector = get_drift_detector()
    report = detector.check_drift()
    return {
        "queue_depth": 0,
        "threshold": max_confidence,
        "items": [],
        "drift_status": {
            "any_drift": report.any_drift,
            "alert_count": len(report.alerts),
        },
    }


@router.post("/review/{extraction_id}/label")
async def label_extraction(extraction_id: int, correct: bool, confidence: float = 0.0) -> dict:
    """
    Accept a human label for a low-confidence extraction.
    Records the sample in the calibrator and optionally feeds it back to the
    fine-tuning dataset builder.
    """
    if not 0.0 <= confidence <= 1.0:
        raise HTTPException(status_code=422, detail="confidence must be in [0.0, 1.0]")
    if confidence > 0:
        _calibrator.add_sample(confidence=confidence, correct=correct)
    return {
        "extraction_id": extraction_id,
        "labeled": True,
        "correct": correct,
        "calibration_samples": _calibrator.sample_count,
    }
