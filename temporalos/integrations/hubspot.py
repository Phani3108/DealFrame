"""HubSpot integration — sync extracted video intelligence as an Engagement.

Creates a Note or Call Engagement on a Contact or Company in HubSpot.

Required env vars:
  HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET
  HUBSPOT_REDIRECT_URI
  HUBSPOT_ACCESS_TOKEN  (private app token or OAuth access token)
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, List, Optional

from temporalos.integrations.base import http_post, http_get

logger = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"


def build_auth_url(client_id: str, redirect_uri: str,
                   scope: str = "crm.objects.contacts.write crm.objects.companies.write",
                   state: str = "") -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    return "https://app.hubspot.com/oauth/authorize?" + urllib.parse.urlencode(params)


def exchange_code(client_id: str, client_secret: str,
                  redirect_uri: str, code: str) -> Dict[str, Any]:
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    _, resp = http_post(
        f"{HUBSPOT_API}/oauth/v1/token",
        payload,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp  # access_token, refresh_token, expires_in


def _auth_header(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def create_note_engagement(
    access_token: str,
    body: str,
    contact_ids: Optional[List[str]] = None,
    company_ids: Optional[List[str]] = None,
    deal_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a Note engagement in HubSpot (CRM v3 engagements API)."""
    associations: List[Dict] = []
    for cid in (contact_ids or []):
        associations.append({"to": {"id": cid}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 10}]})
    for coid in (company_ids or []):
        associations.append({"to": {"id": coid}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
    for did in (deal_ids or []):
        associations.append({"to": {"id": did}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]})

    payload: Dict[str, Any] = {
        "properties": {
            "hs_note_body": body[:65535],
            "hs_timestamp": str(int(__import__("time").time() * 1000)),
        }
    }
    if associations:
        payload["associations"] = associations

    status, resp = http_post(
        f"{HUBSPOT_API}/crm/v3/objects/notes",
        payload,
        _auth_header(access_token),
    )
    return {"http_status": status, "note_id": resp.get("id"), "properties": resp.get("properties")}


def build_note_body(job_id: str, intel: Dict[str, Any]) -> str:
    segs = intel.get("segments", [])
    risk = round(intel.get("overall_risk_score", 0) * 100)
    objections: List[str] = []
    signals: List[str] = []
    for s in segs:
        ext = s.get("extraction", s)
        objections.extend(ext.get("objections", []))
        signals.extend(ext.get("decision_signals", []))

    parts = [
        f"<b>TemporalOS Video Analysis</b> — Job: {job_id}",
        f"Segments: {len(segs)} | Risk: {risk}%",
        "<br><b>Objections:</b> " + ("; ".join(list(dict.fromkeys(objections))[:5]) or "None"),
        "<b>Decision Signals:</b> " + ("; ".join(list(dict.fromkeys(signals))[:5]) or "None"),
    ]
    return "<br>".join(parts)


def sync_job(
    access_token: str,
    job_id: str,
    intel: Dict[str, Any],
    contact_ids: Optional[List[str]] = None,
    company_ids: Optional[List[str]] = None,
    deal_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    body = build_note_body(job_id, intel)
    return create_note_engagement(access_token, body, contact_ids, company_ids, deal_ids)
