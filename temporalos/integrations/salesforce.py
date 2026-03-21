"""Salesforce integration — sync extracted video intelligence to Salesforce CRM.

Creates a Task (Activity) against the relevant Contact or Opportunity, and
optionally updates a custom "Video Call Summary" field.

Required env vars:
  SALESFORCE_CLIENT_ID / SALESFORCE_CLIENT_SECRET
  SALESFORCE_REDIRECT_URI
  SALESFORCE_INSTANCE_URL  (e.g. https://yourorg.my.salesforce.com)
  SALESFORCE_ACCESS_TOKEN  (for server-to-server / long-lived tokens)
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, List, Optional

from temporalos.integrations.base import http_post, http_get

logger = logging.getLogger(__name__)


def build_auth_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    """Step 1 of Web Server OAuth flow."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "api refresh_token offline_access",
    }
    return "https://login.salesforce.com/services/oauth2/authorize?" + urllib.parse.urlencode(params)


def exchange_code(client_id: str, client_secret: str,
                  redirect_uri: str, code: str) -> Dict[str, Any]:
    """Step 2 — exchange authorization code for tokens."""
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    status, resp = http_post(
        "https://login.salesforce.com/services/oauth2/token",
        payload,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp  # contains access_token, instance_url, refresh_token


def refresh_token(client_id: str, client_secret: str,
                  refresh: str, instance_url: str) -> Dict[str, Any]:
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
    }
    status, resp = http_post(
        f"{instance_url}/services/oauth2/token",
        payload,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp


def create_task(
    instance_url: str,
    access_token: str,
    who_id: str,           # Contact / Lead ID
    what_id: str,          # Opportunity / Account ID
    subject: str,
    description: str,
    status: str = "Completed",
) -> Dict[str, Any]:
    """Create a Salesforce Task (Activity) linked to an object."""
    sf_api = f"{instance_url}/services/data/v57.0"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "Subject": subject[:255],
        "Description": description[:32000],
        "Status": status,
        "Type": "Call",
    }
    if who_id:
        payload["WhoId"] = who_id
    if what_id:
        payload["WhatId"] = what_id

    http_status, resp = http_post(f"{sf_api}/sobjects/Task", payload, headers)
    return {"http_status": http_status, "task_id": resp.get("id"), "success": resp.get("success")}


def build_description(job_id: str, intel: Dict[str, Any]) -> str:
    """Format VideoIntelligence as a Salesforce task description."""
    segs = intel.get("segments", [])
    risk = round(intel.get("overall_risk_score", 0) * 100)
    objections: List[str] = []
    signals: List[str] = []
    for s in segs:
        ext = s.get("extraction", s)
        objections.extend(ext.get("objections", []))
        signals.extend(ext.get("decision_signals", []))

    lines = [
        f"TemporalOS Video Analysis — Job: {job_id}",
        f"Segments analyzed: {len(segs)}",
        f"Overall risk score: {risk}%",
        "",
        "Top Objections:",
        *([f"  • {o}" for o in list(dict.fromkeys(objections))[:5]] or ["  None"]),
        "",
        "Decision Signals:",
        *([f"  • {s}" for s in list(dict.fromkeys(signals))[:5]] or ["  None"]),
    ]
    return "\n".join(lines)


def sync_job(
    instance_url: str,
    access_token: str,
    job_id: str,
    intel: Dict[str, Any],
    who_id: str = "",
    what_id: str = "",
) -> Dict[str, Any]:
    """One-shot sync: create a Task in Salesforce for this job."""
    description = build_description(job_id, intel)
    risk_pct = round(intel.get("overall_risk_score", 0) * 100)
    subject = f"Video Call Analysis — Risk {risk_pct}% (Job {job_id[:8]})"
    return create_task(instance_url, access_token, who_id, what_id, subject, description)
