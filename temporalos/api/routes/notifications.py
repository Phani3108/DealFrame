"""Notification API routes — fetch, mark read, count."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    user_id: str = Query("default", description="User ID"),
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Get notifications for a user."""
    from ...notifications import get_notification_service
    svc = get_notification_service()
    if unread_only:
        notifs = svc.get_unread(user_id, limit)
    else:
        notifs = svc.get_all(user_id, limit)
    return {
        "notifications": [n.to_dict() for n in notifs],
        "unread_count": svc.unread_count(user_id),
    }


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str = Query("default"),
) -> dict:
    """Mark a notification as read."""
    from ...notifications import get_notification_service
    svc = get_notification_service()
    success = svc.mark_read(user_id, notification_id)
    return {"success": success}


@router.post("/read-all")
async def mark_all_read(user_id: str = Query("default")) -> dict:
    """Mark all notifications as read."""
    from ...notifications import get_notification_service
    svc = get_notification_service()
    count = svc.mark_all_read(user_id)
    return {"marked_read": count}
