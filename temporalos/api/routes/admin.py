"""Admin API routes — tenant management, RBAC, user management, settings."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateTenantRequest(BaseModel):
    tenant_id: str
    slug: str
    plan: str = "free"
    settings: dict = {}


class UpdateUserRoleRequest(BaseModel):
    email: str
    role: str


# ── Tenant Management ────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants() -> dict:
    from ...enterprise.multi_tenant import list_tenants
    tenants = list_tenants()
    return {
        "tenants": [
            {"tenant_id": t.tenant_id, "slug": t.tenant_slug, "plan": t.plan,
             "max_videos": t.max_videos, "max_users": t.max_users, "settings": t.settings}
            for t in tenants
        ],
        "total": len(tenants),
    }


@router.post("/tenants")
async def create_tenant(req: CreateTenantRequest) -> dict:
    from ...enterprise.multi_tenant import register_tenant
    try:
        ctx = register_tenant(req.tenant_id, req.slug, req.plan, req.settings)
        return {"tenant": {"tenant_id": ctx.tenant_id, "slug": ctx.tenant_slug, "plan": ctx.plan}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── User Management ──────────────────────────────────────────────────────────

@router.get("/users")
async def list_users() -> dict:
    from ...auth import _users
    users = [
        {"email": email, "display_name": u.get("display_name", ""),
         "role": u.get("role", "analyst"), "tier": u.get("tier", "free"),
         "created_at": u.get("created_at", "")}
        for email, u in _users.items()
    ]
    return {"users": users, "total": len(users)}


# ── RBAC ──────────────────────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles() -> dict:
    from ...enterprise.rbac import ROLE_PERMISSIONS
    return {
        "roles": {
            role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()
        },
    }


@router.get("/permissions/{role}")
async def get_permissions(role: str) -> dict:
    from ...enterprise.rbac import ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS.get(role)
    if perms is None:
        raise HTTPException(status_code=404, detail=f"Role '{role}' not found")
    return {"role": role, "permissions": sorted(perms)}


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings() -> dict:
    from ...config import get_settings
    s = get_settings()
    return {
        "app": {"name": s.app.name, "env": s.app.env},
        "database": {"url": "***"},  # masked
        "video": {"frame_interval": s.video.frame_interval_seconds, "max_resolution": s.video.max_resolution},
        "audio": {"whisper_model": s.audio.whisper_model, "language": s.audio.language},
        "extraction": {"default_model": s.extraction.default_model},
        "telemetry": {"enabled": s.telemetry.enabled, "service_name": s.telemetry.service_name},
    }


# ── System Stats ──────────────────────────────────────────────────────────────

@router.get("/stats")
async def system_stats() -> dict:
    from ...enterprise.audit import get_audit_trail
    from ...notifications import get_notification_service
    from ...intelligence.annotations import get_annotation_store
    from ...intelligence.active_learning import get_active_learning_queue
    from ...auth import _users
    from ...enterprise.multi_tenant import list_tenants

    trail = get_audit_trail()
    svc = get_notification_service()
    store = get_annotation_store()
    q = get_active_learning_queue()

    return {
        "users": len(_users),
        "tenants": len(list_tenants()),
        "audit_entries": trail.count(),
        "annotations": store.count,
        "review_queue_pending": q.pending_count,
        "review_queue_total": len(q._items),
    }
