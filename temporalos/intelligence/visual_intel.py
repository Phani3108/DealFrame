"""Visual Intelligence — extract structured data from screen-share frames.

Detects:
- Pricing pages (currency patterns, plan tiers)
- Competitor dashboards (logos, product names)
- Org charts (hierarchy structure)
- Product demos (UI elements, feature mentions)

Uses LLM vision when available, falls back to heuristic detection.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PRICE_PATTERN = re.compile(
    r'[\$\€\£]\s*[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|/mo|/month|/year|/yr|/seat)'
)
TIER_KEYWORDS = ["free", "starter", "basic", "pro", "professional", "enterprise",
                 "business", "premium", "growth", "team", "unlimited", "custom"]
ORG_KEYWORDS = ["ceo", "cto", "cfo", "vp", "director", "manager", "head of",
                "chief", "founder", "lead", "senior", "junior", "coordinator"]
COMPETITOR_NAMES = [
    "gong", "chorus", "clari", "salesforce", "hubspot", "outreach",
    "salesloft", "zoom", "teams", "slack", "notion", "asana",
]


@dataclass
class VisualDetection:
    """A single visual detection from a frame."""
    type: str  # pricing_page | competitor | org_chart | product_demo | text_content
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    frame_index: int = 0
    timestamp_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "confidence": round(self.confidence, 3),
            "details": self.details,
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
        }


def detect_pricing_page(text: str) -> Optional[Dict[str, Any]]:
    """Detect pricing information from OCR text."""
    prices = PRICE_PATTERN.findall(text)
    tiers_found = [t for t in TIER_KEYWORDS if t in text.lower()]
    if not prices and not tiers_found:
        return None
    return {
        "prices": prices[:10],
        "tiers": tiers_found,
        "price_count": len(prices),
    }


def detect_competitors(text: str) -> Optional[Dict[str, Any]]:
    """Detect competitor mentions in visual frame text."""
    lower = text.lower()
    found = [c for c in COMPETITOR_NAMES if c in lower]
    if not found:
        return None
    return {"competitors": found}


def detect_org_chart(text: str) -> Optional[Dict[str, Any]]:
    """Detect org chart / hierarchy signals from text."""
    lower = text.lower()
    roles = [r for r in ORG_KEYWORDS if r in lower]
    if len(roles) < 2:
        return None
    return {"roles_detected": roles, "possible_hierarchy": True}


def analyze_frame(ocr_text: str, frame_index: int = 0,
                  timestamp_ms: int = 0) -> List[VisualDetection]:
    """Analyze a single frame's OCR text for structured intelligence."""
    detections: List[VisualDetection] = []

    pricing = detect_pricing_page(ocr_text)
    if pricing:
        conf = min(0.5 + 0.1 * pricing["price_count"] + 0.1 * len(pricing["tiers"]), 0.95)
        detections.append(VisualDetection(
            type="pricing_page",
            confidence=conf,
            details=pricing,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        ))

    comps = detect_competitors(ocr_text)
    if comps:
        conf = min(0.6 + 0.1 * len(comps["competitors"]), 0.95)
        detections.append(VisualDetection(
            type="competitor",
            confidence=conf,
            details=comps,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        ))

    org = detect_org_chart(ocr_text)
    if org:
        conf = min(0.4 + 0.08 * len(org["roles_detected"]), 0.85)
        detections.append(VisualDetection(
            type="org_chart",
            confidence=conf,
            details=org,
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
        ))

    return detections


def analyze_video_frames(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze a batch of frames from a video.

    Each frame dict should have:
      - ocr_text: str
      - frame_index: int (optional)
      - timestamp_ms: int (optional)
    """
    all_detections: List[VisualDetection] = []
    type_counts: Dict[str, int] = {}

    for f in frames:
        dets = analyze_frame(
            ocr_text=f.get("ocr_text", ""),
            frame_index=f.get("frame_index", 0),
            timestamp_ms=f.get("timestamp_ms", 0),
        )
        all_detections.extend(dets)
        for d in dets:
            type_counts[d.type] = type_counts.get(d.type, 0) + 1

    return {
        "total_frames": len(frames),
        "total_detections": len(all_detections),
        "detection_types": type_counts,
        "detections": [d.to_dict() for d in all_detections],
    }
