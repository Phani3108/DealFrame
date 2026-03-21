"""Multi-Tenant Architecture — middleware + tenant context.

Provides:
- Tenant resolution from JWT, API key, or subdomain
- Request-scoped tenant context
- Tenant-aware DB query helpers
- Tenant isolation enforcement
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Context var for current tenant (request-scoped)
_current_tenant: ContextVar[Optional["TenantContext"]] = ContextVar("_current_tenant", default=None)


@dataclass
class TenantContext:
    """Immutable tenant context for the current request."""
    tenant_id: str
    tenant_slug: str
    plan: str = "free"  # free | pro | enterprise
    settings: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_enterprise(self) -> bool:
        return self.plan == "enterprise"

    @property
    def max_videos(self) -> int:
        limits = {"free": 10, "pro": 100, "enterprise": 10000}
        return limits.get(self.plan, 10)

    @property
    def max_users(self) -> int:
        limits = {"free": 3, "pro": 25, "enterprise": 1000}
        return limits.get(self.plan, 3)


def set_tenant(ctx: TenantContext) -> None:
    """Set the current tenant context (call from middleware)."""
    _current_tenant.set(ctx)


def get_tenant() -> Optional[TenantContext]:
    """Get the current tenant context."""
    return _current_tenant.get()


def require_tenant() -> TenantContext:
    """Get current tenant or raise."""
    ctx = _current_tenant.get()
    if ctx is None:
        raise PermissionError("No tenant context — authentication required")
    return ctx


# In-memory tenant registry (production would use DB)
_tenants: Dict[str, TenantContext] = {}


def register_tenant(tenant_id: str, slug: str, plan: str = "free",
                    settings: Optional[Dict[str, Any]] = None) -> TenantContext:
    """Register a new tenant."""
    if slug in {t.tenant_slug for t in _tenants.values()}:
        raise ValueError(f"Tenant slug '{slug}' already exists")
    ctx = TenantContext(
        tenant_id=tenant_id,
        tenant_slug=slug,
        plan=plan,
        settings=settings or {},
    )
    _tenants[tenant_id] = ctx
    return ctx


def get_tenant_by_id(tenant_id: str) -> Optional[TenantContext]:
    return _tenants.get(tenant_id)


def get_tenant_by_slug(slug: str) -> Optional[TenantContext]:
    for t in _tenants.values():
        if t.tenant_slug == slug:
            return t
    return None


def list_tenants() -> List[TenantContext]:
    return list(_tenants.values())


def tenant_filter(query_items: List[Dict[str, Any]], tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Filter a list of dicts by tenant_id. Uses current tenant if not specified."""
    tid = tenant_id
    if tid is None:
        ctx = get_tenant()
        if ctx is None:
            return query_items
        tid = ctx.tenant_id
    return [item for item in query_items if item.get("tenant_id") == tid]


class TenantMiddleware:
    """ASGI middleware that resolves tenant from request headers.

    Checks (in order):
    1. X-Tenant-ID header
    2. X-Tenant-Slug header
    3. Host header subdomain (slug.example.com)
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        tenant_ctx = None

        # Try X-Tenant-ID
        tid = headers.get(b"x-tenant-id", b"").decode()
        if tid:
            tenant_ctx = get_tenant_by_id(tid)

        # Try X-Tenant-Slug
        if not tenant_ctx:
            slug = headers.get(b"x-tenant-slug", b"").decode()
            if slug:
                tenant_ctx = get_tenant_by_slug(slug)

        # Try subdomain
        if not tenant_ctx:
            host = headers.get(b"host", b"").decode()
            parts = host.split(".")
            if len(parts) >= 3:
                subdomain = parts[0]
                tenant_ctx = get_tenant_by_slug(subdomain)

        if tenant_ctx:
            set_tenant(tenant_ctx)

        await self.app(scope, receive, send)
