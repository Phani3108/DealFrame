"""Webhooks API routes — register and manage webhook endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...webhooks.models import WebhookConfig, WebhookEvent, get_webhook_registry
from ...webhooks.deliverer import get_webhook_deliverer

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreateRequest(BaseModel):
    url: str
    events: List[str]
    secret: str = ""
    description: str = ""


class WebhookUpdateRequest(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    secret: Optional[str] = None
    active: Optional[bool] = None
    description: Optional[str] = None


@router.get("")
async def list_webhooks() -> dict:
    registry = get_webhook_registry()
    webhooks = registry.list_webhooks()
    return {"webhooks": [w.to_dict() for w in webhooks], "total": len(webhooks)}


@router.post("")
async def create_webhook(req: WebhookCreateRequest) -> dict:
    valid_events = {e.value for e in WebhookEvent}
    for evt in req.events:
        if evt not in valid_events:
            raise HTTPException(400, f"Invalid event '{evt}'. Valid: {sorted(valid_events)}")

    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    registry = get_webhook_registry()
    webhook = WebhookConfig(
        url=req.url,
        events=[WebhookEvent(e) for e in req.events],
        secret=req.secret,
        description=req.description,
    )
    created = registry.create(webhook)
    return {"webhook": created.to_dict()}


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str) -> dict:
    registry = get_webhook_registry()
    webhook = registry.get(webhook_id)
    if not webhook:
        raise HTTPException(404, f"Webhook '{webhook_id}' not found")
    return {"webhook": webhook.to_dict()}


@router.patch("/{webhook_id}")
async def update_webhook(webhook_id: str, req: WebhookUpdateRequest) -> dict:
    registry = get_webhook_registry()
    webhook = registry.get(webhook_id)
    if not webhook:
        raise HTTPException(404, f"Webhook '{webhook_id}' not found")

    if req.url is not None:
        webhook.url = req.url
    if req.events is not None:
        valid_events = {e.value for e in WebhookEvent}
        for evt in req.events:
            if evt not in valid_events:
                raise HTTPException(400, f"Invalid event '{evt}'")
        webhook.events = [WebhookEvent(e) for e in req.events]
    if req.secret is not None:
        webhook.secret = req.secret
    if req.active is not None:
        webhook.active = req.active
    if req.description is not None:
        webhook.description = req.description

    updated = registry.update(webhook)
    return {"webhook": updated.to_dict()}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str) -> dict:
    registry = get_webhook_registry()
    ok = registry.delete(webhook_id)
    if not ok:
        raise HTTPException(404, f"Webhook '{webhook_id}' not found")
    return {"deleted": True, "webhook_id": webhook_id}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str) -> dict:
    """Send a test ping to a registered webhook URL."""
    registry = get_webhook_registry()
    webhook = registry.get(webhook_id)
    if not webhook:
        raise HTTPException(404, f"Webhook '{webhook_id}' not found")

    deliverer = get_webhook_deliverer()
    results = deliverer.deliver(
        WebhookEvent.JOB_COMPLETED,
        {"test": True, "webhook_id": webhook_id, "message": "TemporalOS webhook test"},
    )
    return {"webhook_id": webhook_id, "delivery_results": results}


@router.get("/events/types")
async def list_event_types() -> dict:
    return {"events": [e.value for e in WebhookEvent]}
