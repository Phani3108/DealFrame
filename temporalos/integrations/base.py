"""Integration base layer — shared HTTP helpers and connection management."""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.parse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def http_post(url: str, payload: Dict[str, Any],
              headers: Optional[Dict[str, str]] = None,
              timeout: int = 15) -> tuple[int, dict]:
    """Simple POST via stdlib urllib. Returns (status_code, response_body_dict)."""
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw.decode(errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        logger.error("http_post %s failed: %s", url, e)
        return 0, {"error": str(e)}


def http_get(url: str, params: Optional[Dict[str, str]] = None,
             headers: Optional[Dict[str, str]] = None,
             timeout: int = 15) -> tuple[int, dict]:
    """Simple GET via stdlib urllib."""
    full_url = url
    if params:
        full_url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full_url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw.decode(errors="replace")}
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        logger.error("http_get %s failed: %s", url, e)
        return 0, {"error": str(e)}
