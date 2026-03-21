"""Live Copilot API routes — real-time coaching signals for live calls."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/copilot", tags=["copilot"])


class CopilotRequest(BaseModel):
    transcript_so_far: str
    segments_so_far: list[dict] = []
    rep_id: str = "default"
    context: dict = {}


@router.post("/analyze")
async def analyze_live(req: CopilotRequest) -> dict:
    """Analyze current call state and return coaching signals."""
    from ...intelligence.copilot import LiveCopilot
    copilot = LiveCopilot()
    # Build a synthetic segment from the transcript
    segment = {
        "transcript": req.transcript_so_far,
        "extraction": req.context,
        "timestamp_ms": 0,
    }
    prompts = copilot.process_segment(segment)
    return {"signals": [p.to_dict() for p in prompts]}


@router.post("/battlecard")
async def get_battlecard(req: CopilotRequest) -> dict:
    """Get a battlecard for the current call context."""
    from ...intelligence.copilot import LiveCopilot
    copilot = LiveCopilot()
    segment = {
        "transcript": req.transcript_so_far,
        "extraction": req.context,
        "timestamp_ms": 0,
    }
    prompts = copilot.process_segment(segment)
    # Filter to just battlecard type
    cards = [p.to_dict() for p in prompts if p.type == "battlecard"]
    return {"battlecard": cards[0] if cards else None}


@router.get("/config")
async def copilot_config() -> dict:
    """Get copilot configuration and available signal types."""
    return {
        "signal_types": ["objection_alert", "risk_warning", "closing_prompt", "pace_alert", "battlecard"],
        "enabled": True,
        "refresh_interval_ms": 3000,
    }
