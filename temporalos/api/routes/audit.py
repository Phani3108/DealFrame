"""Audit Trail API routes — query and search audit logs."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def query_audit(
    user_id: str = Query("", description="Filter by user"),
    tenant_id: str = Query("", description="Filter by tenant"),
    action: str = Query("", description="Filter by action"),
    resource_type: str = Query("", description="Filter by resource type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    from ...enterprise.audit import get_audit_trail
    trail = get_audit_trail()
    entries = trail.query(
        user_id=user_id, tenant_id=tenant_id,
        action=action, resource_type=resource_type,
        limit=limit, offset=offset,
    )
    return {
        "entries": [e.to_dict() for e in entries],
        "total": trail.count(tenant_id),
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
async def audit_stats(tenant_id: str = Query("")) -> dict:
    from ...enterprise.audit import get_audit_trail
    trail = get_audit_trail()
    entries = trail.query(tenant_id=tenant_id, limit=10000)
    action_counts: dict[str, int] = {}
    resource_counts: dict[str, int] = {}
    for e in entries:
        action_counts[e.action] = action_counts.get(e.action, 0) + 1
        resource_counts[e.resource_type] = resource_counts.get(e.resource_type, 0) + 1
    return {
        "total_entries": trail.count(tenant_id),
        "action_counts": action_counts,
        "resource_counts": resource_counts,
    }
