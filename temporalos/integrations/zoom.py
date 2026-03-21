"""Zoom recording webhook integration.

Zoom sends a POST to our endpoint when a cloud recording is completed.
We verify the signature, extract the recording URL, and submit for processing.

Zoom App credentials are sourced from environment variables:
  ZOOM_WEBHOOK_SECRET_TOKEN — used to verify incoming webhook payloads
  ZOOM_OAUTH_TOKEN         — used to download protected recording files

Webhook event handled: recording.completed
  https://developers.zoom.us/docs/api/rest/reference/zoom-api/events/#tag/Recording/operation/recordingCompleted
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def verify_zoom_signature(
    secret_token: str,
    timestamp: str,
    message: str,
    received_hash: str,
) -> bool:
    """Verify an incoming Zoom webhook payload (v2 signature scheme).

    Reference: https://developers.zoom.us/docs/api/rest/webhook-reference/#verify-webhook-events
    """
    plain = f"v0:{timestamp}:{message}"
    expected = "v0=" + hmac.new(
        secret_token.encode(), plain.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_hash)


def parse_recording_completed(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract recording details from a recording.completed webhook payload.

    Returns a dict with:
        topic         — meeting name
        meeting_id    — Zoom meeting ID
        host_email    — organizer email
        download_url  — first MP4 recording file URL (None if only audio)
        file_type     — 'MP4' | 'M4A' | etc.
        duration_min  — meeting duration in minutes
    """
    obj = payload.get("payload", {}).get("object", {})
    if not obj:
        return None

    files = obj.get("recording_files", [])
    video_file = next(
        (f for f in files if f.get("file_type") in ("MP4", "mp4")),
        files[0] if files else None,
    )

    if not video_file:
        return None

    return {
        "topic": obj.get("topic", "Zoom Recording"),
        "meeting_id": obj.get("id"),
        "host_email": obj.get("host_email"),
        "download_url": video_file.get("download_url"),
        "file_type": video_file.get("file_type"),
        "duration_min": obj.get("duration", 0),
        "start_time": obj.get("start_time"),
    }


def build_zoom_auth_header(oauth_token: str) -> Dict[str, str]:
    """Build Authorization header for downloading Zoom recording files."""
    return {"Authorization": f"Bearer {oauth_token}"}
