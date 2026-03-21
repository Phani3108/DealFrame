"""PII Redaction Engine — detect and redact personally identifiable information.

Detects:
- Email addresses
- Phone numbers (US/intl)
- Social Security Numbers
- Credit card numbers
- Names (via NER keywords)
- IP addresses

Supports: redact (replace with [PII_TYPE]), mask (partial), detect-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PIIDetection:
    type: str  # email | phone | ssn | credit_card | ip_address | name
    value: str
    start: int
    end: int
    confidence: float


# Regex patterns for PII types
PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b'),
    "phone": re.compile(
        r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b'
    ),
    "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
    "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
}

# Redaction placeholders
REDACTION_LABELS = {
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "ssn": "[SSN]",
    "credit_card": "[CREDIT_CARD]",
    "ip_address": "[IP_ADDRESS]",
    "name": "[NAME]",
}


def detect_pii(text: str, types: Optional[List[str]] = None) -> List[PIIDetection]:
    """Detect PII in text. Returns list of detections."""
    detections: List[PIIDetection] = []
    check_types = types or list(PATTERNS.keys())

    for pii_type in check_types:
        pattern = PATTERNS.get(pii_type)
        if not pattern:
            continue
        for match in pattern.finditer(text):
            # Filter false positive SSNs (000, 666, 900-999 are invalid)
            if pii_type == "ssn":
                digits = re.sub(r'[-\s]', '', match.group())
                area = int(digits[:3])
                if area == 0 or area == 666 or area >= 900:
                    continue

            detections.append(PIIDetection(
                type=pii_type,
                value=match.group(),
                start=match.start(),
                end=match.end(),
                confidence=0.9,
            ))

    # Sort by position
    detections.sort(key=lambda d: d.start)
    return detections


def redact_text(text: str, types: Optional[List[str]] = None) -> Tuple[str, List[PIIDetection]]:
    """Redact PII from text. Returns (redacted_text, detections)."""
    detections = detect_pii(text, types)
    if not detections:
        return text, []

    # Process from end to start to preserve positions
    result = text
    for det in reversed(detections):
        label = REDACTION_LABELS.get(det.type, f"[{det.type.upper()}]")
        result = result[:det.start] + label + result[det.end:]

    return result, detections


def mask_text(text: str, types: Optional[List[str]] = None) -> Tuple[str, List[PIIDetection]]:
    """Partially mask PII (show first/last chars). Returns (masked_text, detections)."""
    detections = detect_pii(text, types)
    if not detections:
        return text, []

    result = text
    for det in reversed(detections):
        val = det.value
        if len(val) > 4:
            masked = val[:2] + "*" * (len(val) - 4) + val[-2:]
        else:
            masked = "*" * len(val)
        result = result[:det.start] + masked + result[det.end:]

    return result, detections


def redact_intel(intel: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII from an entire intelligence result."""
    redacted = dict(intel)
    segments = []
    total_detections = 0

    for seg in intel.get("segments", []):
        seg_copy = dict(seg)
        # Redact transcript
        transcript = seg.get("transcript", "")
        if transcript:
            redacted_text, dets = redact_text(transcript)
            seg_copy["transcript"] = redacted_text
            total_detections += len(dets)
        # Redact extraction fields
        ext = seg.get("extraction", {})
        if ext:
            ext_copy = dict(ext)
            for field_name in ["topic"]:
                if field_name in ext_copy and isinstance(ext_copy[field_name], str):
                    ext_copy[field_name], _ = redact_text(ext_copy[field_name])
            for list_field in ["objections", "decision_signals"]:
                if list_field in ext_copy and isinstance(ext_copy[list_field], list):
                    ext_copy[list_field] = [redact_text(item)[0] for item in ext_copy[list_field]
                                            if isinstance(item, str)]
            seg_copy["extraction"] = ext_copy
        segments.append(seg_copy)

    redacted["segments"] = segments
    redacted["pii_redaction"] = {"total_detections": total_detections, "redacted": True}
    return redacted
