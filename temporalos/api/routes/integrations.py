"""Integrations API routes — webhooks in and sync operations out."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ─────────────────────────────── Zoom ────────────────────────────────────────

@router.post("/zoom/webhook")
async def zoom_webhook(request: Request, background: BackgroundTasks) -> dict:
    """Receive Zoom recording.completed webhooks and auto-submit for processing."""
    from ...integrations.zoom import verify_zoom_signature, parse_recording_completed

    body_bytes = await request.body()
    body_str = body_bytes.decode()

    # Verify Zoom signature
    zoom_secret = os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN", "")
    ts = request.headers.get("x-zm-request-timestamp", "")
    sig = request.headers.get("x-zm-signature", "")

    if zoom_secret and not verify_zoom_signature(zoom_secret, ts, body_str, sig):
        raise HTTPException(401, "Invalid Zoom webhook signature")

    import json
    payload = json.loads(body_str)

    # Zoom URL validation challenge
    if payload.get("event") == "endpoint.url_validation":
        token = payload.get("payload", {}).get("plainToken", "")
        enc = hmac.new(zoom_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        return {"plainToken": token, "encryptedToken": enc}

    if payload.get("event") != "recording.completed":
        return {"received": True, "ignored": True}

    parsed = parse_recording_completed(payload)
    background.add_task(_submit_from_url, parsed.get("download_url", ""),
                        {"source": "zoom", "meeting_id": parsed.get("meeting_id")})
    return {"received": True, "queued": True}


# ─────────────────────────────── Teams ───────────────────────────────────────

@router.post("/teams/webhook")
async def teams_webhook(request: Request, background: BackgroundTasks) -> dict:
    from ...integrations.teams import (handle_validation_token,
                                        validate_notification,
                                        parse_call_record_notification)
    import json
    body_bytes = await request.body()
    payload = json.loads(body_bytes)

    # Graph API subscription validation
    vt = handle_validation_token(payload)
    if vt:
        return {"validationToken": vt}

    client_state = os.getenv("TEAMS_CLIENT_STATE", "")
    if not validate_notification(payload, client_state):
        raise HTTPException(401, "Invalid Teams notification")

    records = parse_call_record_notification(payload)
    for rec in records:
        background.add_task(_fetch_and_submit_teams_recording, rec)

    return {"received": True, "records": len(records)}


# ─────────────────────────────── Slack ───────────────────────────────────────

@router.post("/slack/command")
async def slack_slash_command(request: Request) -> dict:
    """Handle /temporalos slash commands."""
    from ...integrations.slack import verify_slack_signature, parse_slash_command, respond_to_slash
    body_bytes = await request.body()

    slack_secret = os.getenv("SLACK_SIGNING_SECRET", "")
    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")

    if slack_secret and not verify_slack_signature(slack_secret, ts, body_bytes.decode(), sig):
        raise HTTPException(401, "Invalid Slack signature")

    # Parse www-form-urlencoded
    import urllib.parse
    form = dict(urllib.parse.parse_qsl(body_bytes.decode()))
    cmd = parse_slash_command(form)

    return _handle_slack_command(cmd)


# ─────────────────────────────── Google Meet ─────────────────────────────────

@router.get("/meet/oauth/callback")
async def meet_oauth_callback(code: str, state: str = "") -> dict:
    """Handle Google OAuth2 callback — exchange code for tokens (stub)."""
    return {"status": "oauth_received", "note": "Store tokens securely in DB", "state": state}


# ─────────────────────────────── Notion ─────────────────────────────────────

class NotionExportRequest(BaseModel):
    token: str
    database_id: str


@router.post("/notion/export/{job_id}")
async def notion_export(job_id: str, req: NotionExportRequest) -> dict:
    from ...integrations.notion import create_page as notion_create_page

    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    intel = job.get("intelligence") or {}
    result = notion_create_page(req.token, req.database_id, job_id, intel)
    return {"job_id": job_id, "notion": result}


# ─────────────────────────────── Salesforce ──────────────────────────────────

class SFSyncRequest(BaseModel):
    instance_url: str
    access_token: str
    who_id: str = ""
    what_id: str = ""


@router.post("/salesforce/sync/{job_id}")
async def salesforce_sync(job_id: str, req: SFSyncRequest) -> dict:
    from ...integrations.salesforce import sync_job as sf_sync

    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    intel = job.get("intelligence") or {}
    result = sf_sync(req.instance_url, req.access_token, job_id, intel, req.who_id, req.what_id)
    return {"job_id": job_id, "salesforce": result}


# ─────────────────────────────── HubSpot ─────────────────────────────────────

class HubSpotSyncRequest(BaseModel):
    access_token: str
    contact_ids: List[str] = []
    company_ids: List[str] = []
    deal_ids: List[str] = []


@router.post("/hubspot/sync/{job_id}")
async def hubspot_sync(job_id: str, req: HubSpotSyncRequest) -> dict:
    from ...integrations.hubspot import sync_job as hs_sync

    jobs = _get_jobs()
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    intel = job.get("intelligence") or {}
    result = hs_sync(
        req.access_token, job_id, intel,
        req.contact_ids or None, req.company_ids or None, req.deal_ids or None,
    )
    return {"job_id": job_id, "hubspot": result}


# ─────────────────────────────── Zapier ──────────────────────────────────────

class ZapierSubscribeRequest(BaseModel):
    target_url: str
    event: str


@router.post("/zapier/subscribe")
async def zapier_subscribe(req: ZapierSubscribeRequest) -> dict:
    from ...integrations.zapier import get_subscription_manager
    manager = get_subscription_manager()
    sub = manager.subscribe(req.target_url, req.event)
    return sub


@router.delete("/zapier/unsubscribe")
async def zapier_unsubscribe(target_url: str) -> dict:
    from ...integrations.zapier import get_subscription_manager
    manager = get_subscription_manager()
    ok = manager.unsubscribe(target_url)
    return {"unsubscribed": ok, "target_url": target_url}


# ─────────────────────────────── Status ──────────────────────────────────────

@router.get("/status")
async def integration_status() -> dict:
    """Return connection status for all integrations."""
    return {
        "zoom": {"configured": bool(os.getenv("ZOOM_WEBHOOK_SECRET_TOKEN"))},
        "teams": {"configured": bool(os.getenv("TEAMS_CLIENT_STATE"))},
        "slack": {"configured": bool(os.getenv("SLACK_SIGNING_SECRET"))},
        "notion": {"configured": bool(os.getenv("NOTION_INTEGRATION_TOKEN"))},
        "salesforce": {"configured": bool(os.getenv("SALESFORCE_ACCESS_TOKEN"))},
        "hubspot": {"configured": bool(os.getenv("HUBSPOT_ACCESS_TOKEN"))},
        "google_meet": {"configured": bool(os.getenv("GOOGLE_CLIENT_ID"))},
    }


# ─────────────────────────────── Helpers ─────────────────────────────────────

def _get_jobs() -> dict:
    from ...api.routes.process import _jobs  # type: ignore[attr-defined]
    return _jobs


def _submit_from_url(url: str, metadata: Dict[str, Any]) -> None:
    """Background helper: submit a URL to the processing pipeline."""
    if not url:
        return
    logger.info("Auto-submitting %s (%s)", url, metadata)
    # In production: call the pipeline or enqueue a BatchItem
    # For now: log the intent
    pass


def _fetch_and_submit_teams_recording(record: Dict[str, Any]) -> None:
    """Fetch Teams call record via Graph API and submit for processing."""
    call_record_id = record.get("call_record_id", "")
    logger.info("Received Teams call record: %s", call_record_id)
    # TODO: fetch /communications/callRecords/{id}/sessions/transferredTo
    # and extract media file URL, then submit to pipeline
    pass


def _handle_slack_command(cmd: Dict[str, Any]) -> dict:
    from ...integrations.slack import build_risk_alert_blocks, build_digest_blocks
    text = cmd.get("text", "").strip()
    if text.startswith("digest"):
        from ...agents.risk_agent import get_risk_agent
        agent = get_risk_agent()
        deals = agent.list_deals()
        return {
            "response_type": "ephemeral",
            "text": f"Risk digest: {len(deals)} deals tracked",
        }
    if text.startswith("search "):
        query = text[7:].strip()
        return {
            "response_type": "in_channel",
            "text": f"Searching for: {query}",
        }
    return {
        "response_type": "ephemeral",
        "text": "TemporalOS — commands: `digest`, `search <query>`",
    }
