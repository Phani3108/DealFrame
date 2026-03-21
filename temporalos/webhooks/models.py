"""Webhook configuration models."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

WEBHOOKS_DIR = Path(os.environ.get("TEMPORALOS_WEBHOOKS_DIR", "/tmp/temporalos/webhooks"))


class WebhookEvent(str, Enum):
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    HIGH_RISK_DETECTED = "risk.high_detected"
    BATCH_COMPLETED = "batch.completed"
    INTEGRATION_ERROR = "integration.error"


@dataclass
class WebhookConfig:
    id: str
    url: str
    events: List[str]
    secret: str                    # HMAC-SHA256 signing secret
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""

    def to_dict(self, include_secret: bool = False) -> dict:
        d = {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "active": self.active,
            "created_at": self.created_at,
            "description": self.description,
        }
        if include_secret:
            d["secret"] = self.secret
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WebhookConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class WebhookRegistry:
    """File-backed webhook configuration registry."""

    def __init__(self, webhooks_dir: Path = WEBHOOKS_DIR):
        self.dir = webhooks_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def create(self, url: str, events: List[str],
               description: str = "") -> WebhookConfig:
        cfg = WebhookConfig(
            id=uuid.uuid4().hex[:16],
            url=url,
            events=events,
            secret=uuid.uuid4().hex,
            description=description,
        )
        self._save(cfg)
        return cfg

    def get(self, webhook_id: str) -> Optional[WebhookConfig]:
        p = self.dir / f"{webhook_id}.json"
        if not p.exists():
            return None
        return WebhookConfig.from_dict(json.loads(p.read_text()))

    def list(self, event: Optional[str] = None) -> List[WebhookConfig]:
        cfgs = []
        for f in sorted(self.dir.glob("*.json")):
            try:
                cfg = WebhookConfig.from_dict(json.loads(f.read_text()))
                if cfg.active and (event is None or event in cfg.events):
                    cfgs.append(cfg)
            except Exception:
                pass
        return cfgs

    def delete(self, webhook_id: str) -> bool:
        p = self.dir / f"{webhook_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    def _save(self, cfg: WebhookConfig) -> None:
        p = self.dir / f"{cfg.id}.json"
        d = asdict(cfg)
        p.write_text(json.dumps(d, indent=2))


_default_registry: Optional["WebhookRegistry"] = None


def get_webhook_registry() -> WebhookRegistry:
    """Return the process-level WebhookRegistry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = WebhookRegistry()
    return _default_registry
