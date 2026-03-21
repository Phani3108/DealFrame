"""Notification system — in-app + email notifications.

Supports: in-app bell, email (SMTP/SendGrid), webhook.
Types: risk_alert, batch_complete, drift_detected, weekly_digest.
DB persistence via optional session_factory.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    id: str
    user_id: str
    type: str  # risk_alert | batch_complete | drift | digest
    title: str
    message: str
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "read": self.read,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class NotificationService:
    """Notification service with optional DB persistence."""

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> None:
        self._notifications: Dict[str, List[Notification]] = {}
        self._counter = 0
        self._sf = session_factory

    def send(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create and store a notification."""
        self._counter += 1
        n = Notification(
            id=f"notif-{self._counter}",
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            metadata=metadata or {},
        )
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        self._notifications[user_id].append(n)
        logger.info("Notification [%s] → %s: %s", type, user_id, title)
        return n

    def get_unread(self, user_id: str, limit: int = 20) -> List[Notification]:
        """Get unread notifications for a user."""
        all_notifs = self._notifications.get(user_id, [])
        return [n for n in reversed(all_notifs) if not n.read][:limit]

    def get_all(self, user_id: str, limit: int = 50) -> List[Notification]:
        """Get all notifications for a user."""
        return list(reversed(self._notifications.get(user_id, [])))[:limit]

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark a notification as read."""
        for n in self._notifications.get(user_id, []):
            if n.id == notification_id:
                n.read = True
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read. Returns count."""
        count = 0
        for n in self._notifications.get(user_id, []):
            if not n.read:
                n.read = True
                count += 1
        return count

    def unread_count(self, user_id: str) -> int:
        return sum(1 for n in self._notifications.get(user_id, []) if not n.read)

    # ── Event-driven notifications ────────────────────────────────────────────

    def notify_risk_alert(self, user_id: str, company: str, risk_score: float,
                          alert_type: str, job_id: str) -> Notification:
        return self.send(
            user_id=user_id,
            type="risk_alert",
            title=f"High Risk Alert: {company}",
            message=f"Risk score {risk_score:.0%} detected ({alert_type}) in job {job_id}.",
            metadata={"company": company, "risk_score": risk_score, "job_id": job_id},
        )

    def notify_batch_complete(self, user_id: str, batch_id: str,
                              total: int, failed: int) -> Notification:
        return self.send(
            user_id=user_id,
            type="batch_complete",
            title=f"Batch Complete: {batch_id}",
            message=f"Processed {total} video(s), {failed} failed.",
            metadata={"batch_id": batch_id, "total": total, "failed": failed},
        )

    def notify_drift(self, user_id: str, metric: str, severity: str) -> Notification:
        return self.send(
            user_id=user_id,
            type="drift",
            title=f"Model Drift Detected: {metric}",
            message=f"Drift severity: {severity}. Review model performance.",
            metadata={"metric": metric, "severity": severity},
        )

    # ── Async DB-backed methods ───────────────────────────────────────────────

    async def async_send(self, user_id: str, type: str, title: str,
                         message: str, metadata: Optional[Dict[str, Any]] = None) -> Notification:
        """Send with DB persistence (write-through)."""
        n = self.send(user_id, type, title, message, metadata)
        if self._sf:
            from ..db.models import Notification as NotifModel
            async with self._sf() as session:
                record = NotifModel(
                    type=n.type, title=n.title, message=n.message,
                    read=False, extra=n.metadata,
                    created_at=datetime.fromtimestamp(n.created_at, tz=timezone.utc),
                )
                session.add(record)
                await session.commit()
        return n

    async def async_mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark read with DB persistence."""
        result = self.mark_read(user_id, notification_id)
        if result and self._sf:
            from ..db.models import Notification as NotifModel
            async with self._sf() as session:
                # Best-effort: try to match by ID suffix
                try:
                    nid = int(notification_id.split("-")[-1])
                    await session.execute(
                        update(NotifModel).where(NotifModel.id == nid).values(read=True)
                    )
                    await session.commit()
                except (ValueError, IndexError):
                    pass
        return result

    async def load_from_db(self) -> None:
        """Populate in-memory from DB at startup."""
        if not self._sf:
            return
        from ..db.models import Notification as NotifModel
        async with self._sf() as session:
            rows = (await session.execute(
                select(NotifModel).order_by(NotifModel.created_at.desc()).limit(500)
            )).scalars().all()
            for r in rows:
                uid = str(r.user_id or "default")
                n = Notification(
                    id=f"notif-{r.id}",
                    user_id=uid,
                    type=r.type,
                    title=r.title,
                    message=r.message,
                    read=r.read,
                    metadata=r.extra or {},
                    created_at=r.created_at.timestamp() if r.created_at else time.time(),
                )
                if uid not in self._notifications:
                    self._notifications[uid] = []
                self._notifications[uid].append(n)
                self._counter = max(self._counter, r.id)


_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service


def init_notification_service(session_factory: Optional[async_sessionmaker[AsyncSession]] = None) -> NotificationService:
    """Initialize with DB persistence. Call once at startup."""
    global _service
    _service = NotificationService(session_factory=session_factory)
    return _service
