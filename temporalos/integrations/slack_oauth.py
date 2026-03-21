"""Slack OAuth integration — full install flow + slash commands.

Flow: User clicks "Add to Slack" → OAuth2 authorize → callback →
slash commands (/tos search, /tos risk) → Block Kit responses.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

_slack_tokens: Dict[str, Dict[str, Any]] = {}


class SlackOAuth:
    """Manages Slack OAuth2 install flow and API."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        signing_secret: str = "",
        redirect_uri: str = "http://localhost:8000/api/v1/integrations/slack/callback",
        scopes: str = "commands,chat:write,incoming-webhook",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.signing_secret = signing_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    def get_install_url(self, state: str = "") -> str:
        """Generate the Slack OAuth2 install URL."""
        params = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state
        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for bot token."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    raise ValueError(f"Slack OAuth failed: {data.get('error', 'unknown')}")
                return data

    def verify_request(self, body: bytes, signature: str, timestamp: str) -> bool:
        """Verify Slack request signature."""
        if not self.signing_secret:
            return False
        # Check timestamp freshness (5-minute window)
        try:
            if abs(time.time() - int(timestamp)) > 300:
                return False
        except (ValueError, TypeError):
            return False

        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def send_message(self, token: str, channel: str, text: str = "",
                           blocks: Optional[list] = None) -> Dict[str, Any]:
        """Send a message to a Slack channel."""
        import aiohttp

        payload: Dict[str, Any] = {"channel": channel}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            ) as resp:
                return await resp.json()

    def store_tokens(self, team_id: str, tokens: Dict[str, Any]) -> None:
        _slack_tokens[team_id] = tokens

    def get_tokens(self, team_id: str) -> Optional[Dict[str, Any]]:
        return _slack_tokens.get(team_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


# ── Slash Command Handlers ─────────────────────────────────────────────────────

def handle_slash_command(command: str, text: str, user_id: str) -> Dict[str, Any]:
    """Route /tos slash commands and return Block Kit response."""
    parts = text.strip().split(None, 1)
    subcommand = parts[0].lower() if parts else "help"
    args = parts[1] if len(parts) > 1 else ""

    handlers = {
        "search": _handle_search,
        "risk": _handle_risk,
        "help": _handle_help,
        "status": _handle_status,
    }

    handler = handlers.get(subcommand, _handle_help)
    return handler(args, user_id)


def _handle_search(query: str, user_id: str) -> Dict[str, Any]:
    """Handle /tos search <query>."""
    if not query:
        return {"text": "Usage: `/tos search <query>`"}

    from temporalos.agents.qa_agent import get_qa_agent
    agent = get_qa_agent()
    answer = agent.ask(query)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "TemporalOS Search"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Q:* {query}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*A:* {answer.answer}"}},
    ]
    if answer.citations:
        cite_text = "\n".join(
            f"• `{c.job_id}` @ {c.timestamp} — {c.topic} (risk: {round(c.risk_score * 100)}%)"
            for c in answer.citations[:3]
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Sources:*\n{cite_text}"}})

    return {"blocks": blocks, "response_type": "in_channel"}


def _handle_risk(args: str, user_id: str) -> Dict[str, Any]:
    """Handle /tos risk — show current alerts."""
    from temporalos.agents.risk_agent import get_risk_agent
    agent = get_risk_agent()
    alerts = agent.run_sweep()

    if not alerts:
        return {"text": "No active risk alerts."}

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Risk Alerts"}},
    ]
    for alert in alerts[:5]:
        d = alert.to_dict()
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": f"*{d.get('company', 'Unknown')}* — {d.get('alert_type', '?')}\n"
                             f"Risk: {round(d.get('risk_score', 0) * 100)}% | {d.get('message', '')}"},
        })

    return {"blocks": blocks, "response_type": "ephemeral"}


def _handle_status(args: str, user_id: str) -> Dict[str, Any]:
    """Handle /tos status."""
    return {"text": "TemporalOS is running. Use `/tos help` for available commands."}


def _handle_help(args: str, user_id: str) -> Dict[str, Any]:
    """Handle /tos help."""
    return {
        "text": "*TemporalOS Slack Commands:*\n"
                "• `/tos search <query>` — Search your video library\n"
                "• `/tos risk` — View current risk alerts\n"
                "• `/tos status` — Check system status\n"
                "• `/tos help` — Show this help message",
    }


def get_slack_oauth() -> SlackOAuth:
    """Get SlackOAuth instance configured from settings."""
    from temporalos.config import get_settings
    s = get_settings()
    return SlackOAuth(
        client_id=getattr(s, "slack_client_id", ""),
        client_secret=getattr(s, "slack_client_secret", ""),
        signing_secret=getattr(s, "slack_signing_secret", ""),
    )
