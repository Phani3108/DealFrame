"""Role-Based Access Control — fine-grained permission enforcement.

Roles: admin, manager, analyst, viewer
Resources: video, extraction, export, settings, users, tenants
Actions: create, read, update, delete, export, admin
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


# Permission definitions
PERMISSIONS = {
    # Video
    "video:create": Permission("video", "create"),
    "video:read": Permission("video", "read"),
    "video:update": Permission("video", "update"),
    "video:delete": Permission("video", "delete"),
    # Extraction
    "extraction:read": Permission("extraction", "read"),
    "extraction:update": Permission("extraction", "update"),
    # Export
    "export:create": Permission("export", "create"),
    "export:read": Permission("export", "read"),
    # Settings
    "settings:read": Permission("settings", "read"),
    "settings:update": Permission("settings", "update"),
    # Users
    "users:read": Permission("users", "read"),
    "users:create": Permission("users", "create"),
    "users:update": Permission("users", "update"),
    "users:delete": Permission("users", "delete"),
    # Tenant
    "tenant:admin": Permission("tenant", "admin"),
    # Annotations
    "annotations:create": Permission("annotations", "create"),
    "annotations:read": Permission("annotations", "read"),
    "annotations:update": Permission("annotations", "update"),
    "annotations:delete": Permission("annotations", "delete"),
}

# Role → permissions mapping
ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "admin": frozenset(PERMISSIONS.keys()),
    "manager": frozenset([
        "video:create", "video:read", "video:update", "video:delete",
        "extraction:read", "extraction:update",
        "export:create", "export:read",
        "settings:read",
        "users:read",
        "annotations:create", "annotations:read", "annotations:update", "annotations:delete",
    ]),
    "analyst": frozenset([
        "video:read",
        "extraction:read", "extraction:update",
        "export:create", "export:read",
        "annotations:create", "annotations:read", "annotations:update",
    ]),
    "viewer": frozenset([
        "video:read",
        "extraction:read",
        "export:read",
        "annotations:read",
    ]),
}


def get_role_permissions(role: str) -> FrozenSet[str]:
    """Get permissions for a role."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, resource: str, action: str) -> bool:
    """Check if a role has a specific permission."""
    perm_key = f"{resource}:{action}"
    return perm_key in get_role_permissions(role)


def check_permission(role: str, resource: str, action: str) -> None:
    """Check permission, raise if denied."""
    if not has_permission(role, resource, action):
        raise PermissionError(
            f"Role '{role}' does not have permission '{resource}:{action}'"
        )


def list_roles() -> List[str]:
    return list(ROLE_PERMISSIONS.keys())


def list_permissions_for_role(role: str) -> List[str]:
    return sorted(get_role_permissions(role))


@dataclass
class RBACPolicy:
    """Custom RBAC policy that can be applied per-tenant."""
    tenant_id: str
    custom_roles: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    def add_custom_role(self, role: str, permissions: List[str]) -> None:
        valid = set()
        for p in permissions:
            if p in PERMISSIONS:
                valid.add(p)
            else:
                logger.warning(f"Unknown permission: {p}")
        self.custom_roles[role] = frozenset(valid)

    def has_permission(self, role: str, resource: str, action: str) -> bool:
        perm_key = f"{resource}:{action}"
        # Check custom roles first
        if role in self.custom_roles:
            return perm_key in self.custom_roles[role]
        # Fall back to global roles
        return has_permission(role, resource, action)

    def check_permission(self, role: str, resource: str, action: str) -> None:
        if not self.has_permission(role, resource, action):
            raise PermissionError(
                f"Role '{role}' does not have permission '{resource}:{action}'"
            )
