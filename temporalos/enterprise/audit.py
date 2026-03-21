"""Audit Trail — log all significant actions for compliance.

Captures:
- User actions (read, create, update, delete)
- Resource type and ID
- Timestamp, IP address, user agent
- Request/response summary
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    id: str
    timestamp: float
    user_id: str
    tenant_id: str
    action: str  # create | read | update | delete | export | login | logout
    resource_type: str  # video | extraction | export | user | settings
    resource_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
        }


class AuditTrail:
    """In-memory audit trail (production would use append-only DB table)."""

    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def log(self, user_id: str, tenant_id: str, action: str,
            resource_type: str, resource_id: str = "",
            details: Optional[Dict[str, Any]] = None,
            ip_address: str = "", user_agent: str = "") -> AuditEntry:
        entry = AuditEntry(
            id=uuid.uuid4().hex[:12],
            timestamp=time.time(),
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._entries.append(entry)
        logger.info(f"AUDIT: {user_id}@{tenant_id} {action} {resource_type}/{resource_id}")
        return entry

    def query(self, user_id: str = "", tenant_id: str = "",
              action: str = "", resource_type: str = "",
              limit: int = 100, offset: int = 0) -> List[AuditEntry]:
        results = self._entries
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if tenant_id:
            results = [e for e in results if e.tenant_id == tenant_id]
        if action:
            results = [e for e in results if e.action == action]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        # Most recent first
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        return results[offset:offset + limit]

    def count(self, tenant_id: str = "") -> int:
        if tenant_id:
            return sum(1 for e in self._entries if e.tenant_id == tenant_id)
        return len(self._entries)

    def clear(self, tenant_id: str = "") -> int:
        if tenant_id:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.tenant_id != tenant_id]
            return before - len(self._entries)
        count = len(self._entries)
        self._entries.clear()
        return count


_trail: Optional[AuditTrail] = None


def get_audit_trail() -> AuditTrail:
    global _trail
    if _trail is None:
        _trail = AuditTrail()
    return _trail


def set_audit_trail(trail: AuditTrail) -> None:
    global _trail
    _trail = trail
