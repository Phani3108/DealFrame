"""Notion export integration.

Creates a Notion database record for each processed video with all
extracted fields as properties.

Environment variables:
  NOTION_INTEGRATION_TOKEN  — Internal integration secret (notion.so/my-integrations)
  NOTION_DATABASE_ID        — Target database ID

OAuth flow (for multi-tenant):
  NOTION_CLIENT_ID / NOTION_CLIENT_SECRET — public integration credentials
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from temporalos.integrations.base import http_post, http_get

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rich_text(text: str) -> List[dict]:
    return [{"type": "text", "text": {"content": str(text)[:2000]}}]


def build_page_properties(job_id: str, intel: Dict[str, Any]) -> Dict[str, Any]:
    """Convert VideoIntelligence dict to Notion page properties."""
    segs = intel.get("segments", [])
    risk = round(intel.get("overall_risk_score", 0) * 100)
    topics = list({s.get("extraction", s).get("topic", "general") for s in segs})
    objections = []
    for s in segs:
        objections.extend(s.get("extraction", s).get("objections", []))
    unique_obj = list(dict.fromkeys(objections))[:5]

    return {
        "Job ID": {"title": _rich_text(job_id)},
        "Risk Score (%)": {"number": risk},
        "Topics": {"multi_select": [{"name": t[:100]} for t in topics[:5]]},
        "Segment Count": {"number": len(segs)},
        "Top Objections": {"rich_text": _rich_text("; ".join(unique_obj) or "None")},
        "Duration (s)": {"number": round(intel.get("duration_ms", 0) / 1000)},
        "Status": {"select": {"name": "Analyzed"}},
    }


def create_page(token: str, database_id: str, job_id: str,
                intel: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Notion database page for a processed video."""
    props = build_page_properties(job_id, intel)
    segs = intel.get("segments", [])
    summary_lines = [
        f"**Job ID**: {job_id}",
        f"**Segments**: {len(segs)}",
        f"**Overall Risk**: {round(intel.get('overall_risk_score', 0) * 100)}%",
    ]

    payload = {
        "parent": {"database_id": database_id},
        "properties": props,
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": _rich_text("\n".join(summary_lines))
                },
            }
        ],
    }
    status, resp = http_post(f"{NOTION_API}/pages", payload, _headers(token))
    if status not in (200, 201):
        logger.error("Notion create_page failed: %s %s", status, resp)
    return {"status": status, "page_id": resp.get("id"), "url": resp.get("url")}


def list_databases(token: str) -> List[Dict[str, Any]]:
    """List all databases the integration has access to."""
    status, resp = http_get(
        f"{NOTION_API}/search",
        params={"filter": '{"value":"database","property":"object"}'},
        headers=_headers(token),
    )
    results = resp.get("results", [])
    return [
        {"id": db.get("id"), "title": db.get("title", [{}])[0].get("plain_text", "Untitled")}
        for db in results
        if db.get("object") == "database"
    ]
