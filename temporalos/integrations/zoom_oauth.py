"""Zoom OAuth integration — full OAuth2 flow + recording webhook processing.

Flow: User clicks "Connect Zoom" → redirect to Zoom authorize → callback with code →
exchange for tokens → receive recording.completed webhooks → auto-download + process.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# In-memory token store (per-user)
_zoom_tokens: Dict[str, Dict[str, Any]] = {}


class ZoomOAuth:
    """Manages Zoom OAuth2 flow and API access."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        redirect_uri: str = "http://localhost:8000/api/v1/integrations/zoom/callback",
        webhook_secret: str = "",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.webhook_secret = webhook_secret

    def get_authorize_url(self, state: str = "") -> str:
        """Generate the Zoom OAuth2 authorization URL."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state
        return f"https://zoom.us/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access + refresh tokens."""
        import aiohttp
        import base64

        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://zoom.us/oauth/token",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ValueError(f"Zoom token exchange failed: {text}")
                return await resp.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token."""
        import aiohttp
        import base64

        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://zoom.us/oauth/token",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ValueError(f"Zoom token refresh failed: {text}")
                return await resp.json()

    def verify_webhook(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """Verify Zoom webhook signature."""
        if not self.webhook_secret:
            return False
        message = f"v0:{timestamp}:{payload.decode()}"
        expected = "v0=" + hmac.new(
            self.webhook_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def get_recording_files(self, access_token: str, meeting_id: str) -> list:
        """Fetch recording files for a meeting."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.zoom.us/v2/meetings/{meeting_id}/recordings",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("recording_files", [])

    def store_tokens(self, user_id: str, tokens: Dict[str, Any]) -> None:
        _zoom_tokens[user_id] = tokens

    def get_tokens(self, user_id: str) -> Optional[Dict[str, Any]]:
        return _zoom_tokens.get(user_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def get_zoom_oauth() -> ZoomOAuth:
    """Get ZoomOAuth instance configured from settings."""
    from temporalos.config import get_settings
    s = get_settings()
    return ZoomOAuth(
        client_id=getattr(s, "zoom_client_id", ""),
        client_secret=getattr(s, "zoom_client_secret", ""),
        webhook_secret=getattr(s, "zoom_webhook_secret", ""),
    )
