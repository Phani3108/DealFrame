"""Pattern Mining API routes — cross-call pattern analysis."""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("")
async def get_patterns(
    pattern_type: str = Query("objection_risk", description="Pattern type: objection_risk|topic_risk|rep_performance|behavioral"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Get mined patterns across all analyzed calls."""
    from ...intelligence.pattern_miner import PatternMiner
    miner = PatternMiner()
    # Get all job segments from process store
    from ...api.routes.process import _jobs
    all_segments = []
    for jid, jdata in _jobs.items():
        result = jdata.get("result", {})
        segs = result.get("segments", [])
        all_segments.extend(segs)
        if segs:
            miner.add_call(jid, result)

    if not all_segments:
        return {"pattern_type": pattern_type, "patterns": [], "total_segments": 0}

    all_patterns = miner.mine_patterns(min_sample_size=1)

    # Filter by pattern_type
    type_map = {
        "objection_risk": "objection",
        "topic_risk": "topic",
        "rep_performance": "rep",
        "behavioral": "behavior",
    }
    target = type_map.get(pattern_type, pattern_type)
    filtered = [p.to_dict() if hasattr(p, "to_dict") else p
                for p in all_patterns if p.category == target]

    return {
        "pattern_type": pattern_type,
        "patterns": filtered[:limit],
        "total_segments": len(all_segments),
    }


@router.get("/summary")
async def pattern_summary() -> dict:
    """Get a summary of all pattern types."""
    from ...api.routes.process import _jobs
    total_jobs = len(_jobs)
    completed = sum(1 for j in _jobs.values() if j.get("status") == "completed")
    total_segments = sum(
        len(j.get("result", {}).get("segments", []))
        for j in _jobs.values()
    )
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed,
        "total_segments": total_segments,
        "available_patterns": ["objection_risk", "topic_risk", "rep_performance", "behavioral"],
    }
