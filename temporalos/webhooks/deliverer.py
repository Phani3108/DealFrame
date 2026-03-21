"""Webhook delivery — HTTP POST with HMAC-SHA256 signature and retry.

Delivery pattern:
  1. Build payload with event type, timestamp, and data.
  2. Sign with HMAC-SHA256 using the webhook's secret.
  3. POST to the registered URL with X-TemporalOS-Signature header.
  4. Retry up to 3 times with exponential backoff on network / 5xx errors.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from temporalos.webhooks.models import WebhookConfig, WebhookEvent, WebhookRegistry

logger = logging.getLogger(__name__)

_registry: Optional[WebhookRegistry] = None


def get_webhook_registry() -> WebhookRegistry:
    global _registry
    if _registry is None:
        _registry = WebhookRegistry()
    return _registry


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(url: str, payload: bytes, headers: Dict[str, str],
          timeout: int = 10) -> int:
    """HTTP POST via urllib (no extra deps). Returns HTTP status code."""
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        logger.warning("Webhook delivery error: %s", e)
        return 0


class WebhookDeliverer:
    """Delivers webhook events to all registered subscribers."""

    def __init__(self, registry: Optional[WebhookRegistry] = None,
                 max_retries: int = 3):
        self.registry = registry or get_webhook_registry()
        self.max_retries = max_retries

    def deliver(self, event: str, data: Dict[str, Any]) -> List[dict]:
        """Deliver *event* to all active webhooks subscribed to it.

        Returns a list of delivery attempt records.
        """
        webhooks = self.registry.list(event=event)
        results = []

        for wh in webhooks:
            result = self._deliver_one(wh, event, data)
            results.append(result)

        return results

    def _deliver_one(self, wh: WebhookConfig, event: str,
                     data: Dict[str, Any]) -> dict:
        payload_dict = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        body = json.dumps(payload_dict).encode()
        sig = _sign(wh.secret, body)
        headers = {
            "Content-Type": "application/json",
            "X-TemporalOS-Signature": f"sha256={sig}",
            "X-TemporalOS-Event": event,
        }

        status = 0
        for attempt in range(1, self.max_retries + 1):
            status = _post(wh.url, body, headers)
            if 200 <= status < 300:
                logger.info("Webhook %s → %s delivered (attempt %d)", wh.id, wh.url, attempt)
                break
            wait = 2 ** attempt
            logger.warning("Webhook %s attempt %d failed (status %d), retry in %ds",
                           wh.id, attempt, status, wait)
            if attempt < self.max_retries:
                time.sleep(wait)

        return {
            "webhook_id": wh.id,
            "url": wh.url,
            "event": event,
            "status": status,
            "success": 200 <= status < 300,
        }


_deliverer: Optional[WebhookDeliverer] = None


def get_webhook_deliverer() -> WebhookDeliverer:
    global _deliverer
    if _deliverer is None:
        _deliverer = WebhookDeliverer()
    return _deliverer
