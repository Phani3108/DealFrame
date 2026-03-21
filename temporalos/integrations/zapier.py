"""Zapier REST Hooks integration.

Implements the Zapier REST Hooks protocol so any Zapier Zap can subscribe
to TemporalOS events (job.completed, risk.high_detected, etc.).

REST Hooks protocol:
  POST /integrations/zapier/subscribe    → register a Zap subscription
  DELETE /integrations/zapier/unsubscribe → remove a subscription
  POST → subscriber URL                  → deliver event payloads

Env vars:
  TEMPORALOS_ZAPIER_HOOK_SECRET — shared secret for payload signing
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List

from temporalos.integrations.base import http_post

logger = logging.getLogger(__name__)


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """HMAC-SHA256 signature for outgoing Zapier payloads."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def build_event_payload(event_name: str, job_id: str,
                        intel: Dict[str, Any]) -> Dict[str, Any]:
    """Build the flat dict Zapier will receive for mapping."""
    segs = intel.get("segments", [])
    risk = round(intel.get("overall_risk_score", 0) * 100)
    objections: List[str] = []
    signals: List[str] = []
    topics = set()
    for s in segs:
        ext = s.get("extraction", s)
        objections.extend(ext.get("objections", []))
        signals.extend(ext.get("decision_signals", []))
        topics.add(ext.get("topic", "general"))

    return {
        "event": event_name,
        "job_id": job_id,
        "risk_score_pct": risk,
        "segment_count": len(segs),
        "top_objections": ", ".join(list(dict.fromkeys(objections))[:3]),
        "decision_signals": ", ".join(list(dict.fromkeys(signals))[:3]),
        "topics": ", ".join(sorted(topics)[:5]),
        "duration_seconds": round(intel.get("duration_ms", 0) / 1000),
    }


def deliver_hook(
    subscriber_url: str,
    event_name: str,
    job_id: str,
    intel: Dict[str, Any],
    secret: str = "",
) -> Dict[str, Any]:
    """POST a REST Hook payload to a Zapier subscriber URL."""
    payload = build_event_payload(event_name, job_id, intel)
    # Zapier expects a list (even for single events)
    body = [payload]

    extra_headers: Dict[str, str] = {}
    if secret:
        raw = json.dumps(body).encode()
        sig = sign_payload(secret, raw)
        extra_headers["X-TemporalOS-Signature"] = sig

    status, resp = http_post(subscriber_url, body, extra_headers)  # type: ignore[arg-type]
    return {"http_status": status, "event": event_name, "job_id": job_id, "subscriber": subscriber_url}


# ---------------------------------------------------------------------------
# Subscription registry (in-memory; use WebhookRegistry for persistence)
# ---------------------------------------------------------------------------

class ZapierSubscriptionManager:
    """Manages Zapier REST Hook subscriptions in-memory.

    For persistence use temporalos.webhooks.WebhookRegistry directly —
    Zapier subscriptions are just webhooks scoped to a specific event.
    """

    def __init__(self) -> None:
        self._subs: Dict[str, Dict[str, str]] = {}  # target_url → {event, target_url}

    def subscribe(self, target_url: str, event: str) -> Dict[str, str]:
        sub_id = hashlib.sha256(f"{target_url}:{event}".encode()).hexdigest()[:16]
        self._subs[sub_id] = {"id": sub_id, "target_url": target_url, "event": event}
        return self._subs[sub_id]

    def unsubscribe(self, target_url: str) -> bool:
        found = [k for k, v in self._subs.items() if v["target_url"] == target_url]
        for k in found:
            del self._subs[k]
        return bool(found)

    def get_subscribers(self, event: str) -> List[Dict[str, str]]:
        return [v for v in self._subs.values() if v["event"] == event]

    def list_all(self) -> List[Dict[str, str]]:
        return list(self._subs.values())


_manager: ZapierSubscriptionManager | None = None


def get_subscription_manager() -> ZapierSubscriptionManager:
    global _manager
    if _manager is None:
        _manager = ZapierSubscriptionManager()
    return _manager
