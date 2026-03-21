"""Audit Trail — log all significant actions for compliance.

Captures:
- User actions (read, create, update, delete)
- Resource type and ID
- Timestamp, IP address, user agent
- Request/response summary

Supports DB persistence via optional session_factory.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    """Audit trail with optional DB persistence.

    When session_factory is None (default), operates purely in-memory
    (backward compatible with all existing tests).
    When session_factory is provided, async methods persist to/load from DB.
    """

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> None:
        self._entries: List[AuditEntry] = []
        self._sf = session_factory

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

    async def async_log(self, user_id: str, tenant_id: str, action: str,
                        resource_type: str, resource_id: str = "",
                        details: Optional[Dict[str, Any]] = None,
                        ip_address: str = "", user_agent: str = "") -> AuditEntry:
        """Log with DB persistence (write-through)."""
        entry = self.log(user_id, tenant_id, action, resource_type,
                         resource_id, details, ip_address, user_agent)
        if self._sf:
            from ..db.models import AuditLog as AuditLogModel
            async with self._sf() as session:
                record = AuditLogModel(
                    action=entry.action,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    details=entry.details,
                    ip_address=entry.ip_address,
                    created_at=datetime.fromtimestamp(entry.timestamp, tz=timezone.utc),
                )
                session.add(record)
                await session.commit()
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
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        return results[offset:offset + limit]

    async def async_query(self, user_id: str = "", tenant_id: str = "",
                          action: str = "", resource_type: str = "",
                          limit: int = 100, offset: int = 0) -> List[AuditEntry]:
        """Query from DB if available, otherwise from memory."""
        if self._sf:
            from ..db.models import AuditLog as AuditLogModel
            async with self._sf() as session:
                stmt = select(AuditLogModel).order_by(AuditLogModel.created_at.desc())
                if action:
                    stmt = stmt.where(AuditLogModel.action == action)
                if resource_type:
                    stmt = stmt.where(AuditLogModel.resource_type == resource_type)
                stmt = stmt.offset(offset).limit(limit)
                rows = (await session.execute(stmt)).scalars().all()
                return [
                    AuditEntry(
                        id=str(r.id),
                        timestamp=r.created_at.timestamp() if r.created_at else 0,
                        user_id=str(r.user_id or ""),
                        tenant_id=str(r.tenant_id or ""),
                        action=r.action,
                        resource_type=r.resource_type,
                        resource_id=r.resource_id,
                        details=r.details or {},
                        ip_address=r.ip_address or "",
                    )
                    for r in rows
                ]
        return self.query(user_id, tenant_id, action, resource_type, limit, offset)

    async def load_from_db(self) -> None:
        """Populate in-memory cache from DB at startup."""
        if not self._sf:
            return
        from ..db.models import AuditLog as AuditLogModel
        async with self._sf() as session:
            rows = (await session.execute(
                select(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(1000)
            )).scalars().all()
            self._entries = [
                AuditEntry(
                    id=str(r.id),
                    timestamp=r.created_at.timestamp() if r.created_at else 0,
                    user_id=str(r.user_id or ""),
                    tenant_id=str(r.tenant_id or ""),
                    action=r.action,
                    resource_type=r.resource_type,
                    resource_id=r.resource_id,
                    details=r.details or {},
                    ip_address=r.ip_address or "",
                )
                for r in rows
            ]

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


def init_audit_trail(session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> AuditTrail:
    """Initialize the audit trail with DB persistence. Call once at startup."""
    global _trail
    _trail = AuditTrail(session_factory=session_factory)
    return _trail


def set_audit_trail(trail: AuditTrail) -> None:
    global _trail
    _trail = trail
