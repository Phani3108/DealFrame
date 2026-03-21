"""Slack bot integration — slash commands, event callbacks, and Block Kit messages.

Features:
  /temporalos search <query>       — search across all video segments
  /temporalos status               — last 5 jobs with risk scores
  /temporalos digest               — daily risk summary
  /temporalos analyze <zoom_url>   — submit a recording URL

Incoming webhooks for proactive alerts (daily digest, high-risk detection).

Environment variables:
  SLACK_BOT_TOKEN          — xoxb-... bot OAuth token
  SLACK_SIGNING_SECRET     — used to verify request signatures
  SLACK_RISK_CHANNEL_ID    — channel for risk alerts
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional

from temporalos.integrations.base import http_post

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


# ── Signature verification ────────────────────────────────────────────────────

def verify_slack_signature(signing_secret: str, timestamp: str,
                            body: str, received_sig: str) -> bool:
    """Verify Slack's request signature (v0 scheme)."""
    if abs(time.time() - float(timestamp)) > 300:
        return False  # Replay attack window
    base = f"v0:{timestamp}:{body}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)


# ── Slash command parsing ────────────────────────────────────────────────────

def parse_slash_command(form_data: Dict[str, str]) -> Dict[str, str]:
    """Parse a Slack slash command form POST body."""
    return {
        "command": form_data.get("command", ""),
        "text": form_data.get("text", "").strip(),
        "user_id": form_data.get("user_id", ""),
        "channel_id": form_data.get("channel_id", ""),
        "response_url": form_data.get("response_url", ""),
    }


# ── Block Kit message builders ───────────────────────────────────────────────

def build_risk_alert_blocks(job_id: str, risk_score: float,
                             top_objections: List[str]) -> List[dict]:
    """Build a Slack Block Kit message for a high-risk call alert."""
    color = "#FF0000" if risk_score > 0.7 else "#FF9900"
    obj_text = "\n".join(f"• {o}" for o in top_objections[:3]) or "None"
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚠️ High Risk Call Detected"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Job ID*\n`{job_id[:16]}…`"},
                {"type": "mrkdwn", "text": f"*Risk Score*\n{round(risk_score * 100)}%"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top Objections*\n{obj_text}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Analysis"},
                    "url": f"http://localhost:8000/results/{job_id}",
                    "style": "primary",
                }
            ],
        },
    ]


def build_digest_blocks(jobs: List[Dict[str, Any]]) -> List[dict]:
    """Build a daily digest Slack message."""
    if not jobs:
        return [{"type": "section",
                 "text": {"type": "mrkdwn", "text": "No calls processed today."}}]

    rows = "\n".join(
        f"• `{j.get('job_id', '')[:12]}…` — "
        f"risk: {round(j.get('risk_score', 0) * 100)}% "
        f"({j.get('status', 'unknown')})"
        for j in jobs[:10]
    )
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"📊 TemporalOS Daily Digest — {len(jobs)} calls"}},
        {"type": "section",
         "text": {"type": "mrkdwn", "text": rows}},
    ]


def build_search_result_blocks(query: str, results: List[Dict[str, Any]]) -> List[dict]:
    """Format search results as Slack blocks."""
    if not results:
        return [{"type": "section",
                 "text": {"type": "mrkdwn",
                          "text": f"No results found for *{query}*"}}]
    items = "\n".join(
        f"• [{r.get('timestamp_str', '?')}] `{r.get('topic', '')}` "
        f"— {r.get('transcript_snippet', '')[:60]}…"
        for r in results[:5]
    )
    return [
        {"type": "section",
         "text": {"type": "mrkdwn", "text": f"*Results for:* _{query}_\n{items}"}},
    ]


# ── API helpers ───────────────────────────────────────────────────────────────

def post_message(token: str, channel: str, text: str = "",
                 blocks: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Post a message to a Slack channel."""
    payload: Dict[str, Any] = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    status, resp = http_post(
        f"{SLACK_API}/chat.postMessage",
        payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return {"status": status, "ok": resp.get("ok", False), "ts": resp.get("ts")}


def respond_to_slash(response_url: str, text: str = "",
                     blocks: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Respond to a slash command via response_url (delayed response)."""
    payload: Dict[str, Any] = {"response_type": "in_channel", "text": text}
    if blocks:
        payload["blocks"] = blocks
    status, resp = http_post(response_url, payload)
    return {"status": status}
