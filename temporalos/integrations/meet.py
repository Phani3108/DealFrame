"""Google Meet / Google Calendar auto-ingest integration.

Flow:
  1. User authorizes via OAuth 2.0 (Google Calendar + Drive scopes).
  2. We set up a Calendar push notification (Google Workspace webhook).
  3. When a calendar event ends, Google sends a channel notification.
  4. We look up the event attendees and recording via the Drive API.
  5. We enqueue the recording URL for TemporalOS processing.

Environment variables:
  GOOGLE_CLIENT_ID      — OAuth client ID
  GOOGLE_CLIENT_SECRET  — OAuth client secret
  GOOGLE_REDIRECT_URI   — OAuth callback URL

NOTE: Requires google-auth and google-api-python-client for prod.
      This module provides the integration logic; OAuth flow is handled in the API route.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def build_auth_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    """Build the Google OAuth 2.0 authorization URL."""
    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def parse_calendar_notification(headers: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Parse a Google Calendar push notification header payload.

    Returns channel_id, resource_id, resource_state, or None if invalid.
    """
    channel_id = headers.get("X-Goog-Channel-ID") or headers.get("x-goog-channel-id")
    resource_id = headers.get("X-Goog-Resource-ID") or headers.get("x-goog-resource-id")
    resource_state = headers.get("X-Goog-Resource-State", "").lower()

    if not channel_id or resource_state not in ("exists", "sync", "not_exists"):
        return None

    return {
        "channel_id": channel_id,
        "resource_id": resource_id,
        "resource_state": resource_state,
    }


def find_recording_in_drive(drive_service: Any, event_summary: str,
                             host_email: str) -> Optional[str]:
    """Search Google Drive for a Meet recording by event name.

    Returns the first matching file's download URL, or None.
    (Requires googleapiclient to be installed for real usage.)
    """
    # In production, call: drive_service.files().list(q=..., fields=...).execute()
    # For now, return None to indicate no recording found via mock
    return None
