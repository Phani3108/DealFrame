"""Microsoft Teams recording integration via Microsoft Graph API.

Flow:
  1. Register a changeNotification subscription on callRecords in Graph API.
  2. Teams sends a POST to our webhook when a call recording is available.
  3. We validate the client state, fetch the recording URL, and enqueue.

Scopes needed: CallRecords.Read.All, OnlineMeetings.Read.All

Environment variables:
  TEAMS_TENANT_ID      — Azure AD tenant ID
  TEAMS_CLIENT_ID      — App registration client ID
  TEAMS_CLIENT_SECRET  — App registration client secret
  TEAMS_WEBHOOK_SECRET — Client state secret for notification validation
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def build_auth_token_request(tenant_id: str, client_id: str,
                              client_secret: str) -> Dict[str, str]:
    """Build client-credentials token request body."""
    return {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }


def validate_notification(payload: Dict[str, Any], client_state: str) -> bool:
    """Validate an incoming Graph change notification by checking clientState."""
    for notif in payload.get("value", []):
        if notif.get("clientState") != client_state:
            logger.warning("Teams webhook clientState mismatch — rejecting notification")
            return False
    return True


def handle_validation_token(payload: Dict[str, Any]) -> Optional[str]:
    """Handle Microsoft's webhook validation challenge.

    When setting up a subscription, Graph sends a POST with validationToken.
    We must echo it back within 10 seconds.
    """
    return payload.get("validationToken")


def parse_call_record_notification(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract call record IDs from a Graph notification payload.

    Returns list of dicts with `call_record_id` and `subscription_id`.
    """
    results: List[Dict[str, str]] = []
    for notif in payload.get("value", []):
        resource = notif.get("resource", "")
        # resource format: "communications/callRecords/{id}"
        parts = resource.rstrip("/").split("/")
        if len(parts) >= 2:
            results.append({
                "call_record_id": parts[-1],
                "subscription_id": notif.get("subscriptionId", ""),
                "change_type": notif.get("changeType", ""),
            })
    return results
