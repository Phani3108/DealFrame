"""Converts a SchemaDefinition into a structured extraction prompt and extractor.

The SchemaBasedExtractor wraps the rule-based engine using field definitions
to filter and map extraction outputs. When an LLM is configured, it builds
a typed JSON prompt asking the model for exactly the defined fields.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from temporalos.extraction.base import BaseExtractionModel, ExtractionResult
from temporalos.schemas.registry import FieldType, SchemaDefinition


def build_prompt_from_schema(schema: SchemaDefinition, transcript: str,
                              ocr_text: str = "") -> str:
    """Build an extraction prompt from a custom schema."""
    field_lines: List[str] = []
    for f in schema.fields:
        opts = f" (one of: {', '.join(f.options)})" if f.options else ""
        req = "" if f.required else " (optional)"
        field_lines.append(
            f'  "{f.name}": <{f.type.value}{opts}> — {f.description}{req}'
        )

    context_block = f"Slide/screen text: {ocr_text}\n" if ocr_text else ""

    return (
        f"You are an expert analyst. Extract the following fields from the meeting segment.\n"
        f"Return ONLY a valid JSON object with exactly these keys:\n"
        + "\n".join(field_lines)
        + f"\n\n{context_block}Transcript:\n{transcript}\n\n"
        f"Schema: {schema.name} — {schema.description}\n"
        f"Respond with a single JSON object only."
    )


def _coerce(value: Any, field_type: FieldType) -> Any:
    """Best-effort type coercion for extracted values."""
    if value is None:
        return None
    if field_type in (FieldType.LIST_STRING, FieldType.LIST_CATEGORY):
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]
    if field_type == FieldType.BOOLEAN:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "yes", "1")
    if field_type == FieldType.NUMBER:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return str(value)


class SchemaBasedExtractor(BaseExtractionModel):
    """
    Extraction model driven by a SchemaDefinition.

    Falls back to rule-based extraction for core fields (topic, sentiment,
    risk, objections, decision_signals) and adds schema-defined fields
    with mock values for testing.
    """

    model_name = "schema-based"

    def __init__(self, schema: SchemaDefinition):
        self.schema = schema

    def extract(self, segment: Any, ocr_text: str = "") -> "ExtractionResult":  # type: ignore[override]
        # Core fields via keyword rules
        if isinstance(segment, str):
            # Called as extract(transcript, ocr_text)
            transcript = segment
        else:
            transcript = segment.transcript if hasattr(segment, "transcript") else str(segment)
            if hasattr(segment, "ocr_text") and not ocr_text:
                ocr_text = segment.ocr_text or ""

        topic = self._infer_topic(transcript)
        risk, risk_score = self._infer_risk(transcript)
        objections = self._infer_objections(transcript)
        signals = self._infer_signals(transcript)

        # Custom fields — populated with placeholder values for rule-based path
        custom_fields: Dict[str, Any] = {}
        for field_def in self.schema.fields:
            if field_def.name in ("topic", "risk", "objections", "decision_signals"):
                continue  # covered by ExtractionResult
            if field_def.options:
                custom_fields[field_def.name] = field_def.options[0]
            elif field_def.type == FieldType.BOOLEAN:
                custom_fields[field_def.name] = False
            elif field_def.type == FieldType.NUMBER:
                custom_fields[field_def.name] = 0.0
            elif field_def.type in (FieldType.LIST_STRING, FieldType.LIST_CATEGORY):
                custom_fields[field_def.name] = []
            else:
                custom_fields[field_def.name] = ""

        result = ExtractionResult(
            topic=topic,
            sentiment="neutral",
            risk=risk,
            risk_score=risk_score,
            objections=objections,
            decision_signals=signals,
            confidence=0.5,
            model_name=self.model_name,
        )
        # Attach custom fields as attributes for downstream use
        result.__dict__.update(custom_fields)
        return result

    # ── Keyword-based helpers ─────────────────────────────────────────────

    _TOPIC_MAP = {
        "pricing": ["price", "cost", "budget", "expensive", "cheap", "discount"],
        "competition": ["competitor", "alternative", "versus", "vs", "other tool"],
        "features": ["feature", "function", "capability", "integration", "api"],
        "timeline": ["when", "deadline", "launch", "schedule", "quarter"],
        "security": ["security", "compliance", "gdpr", "hipaa", "soc2"],
        "onboarding": ["onboard", "setup", "configure", "implement", "deploy"],
        "support": ["support", "help", "issue", "bug", "problem"],
        "general": [],
    }

    def _infer_topic(self, text: str) -> str:
        t = text.lower()
        for topic, keywords in self._TOPIC_MAP.items():
            if any(k in t for k in keywords):
                return topic
        return "general"

    def _infer_risk(self, text: str) -> tuple[str, float]:
        t = text.lower()
        high = ["cancel", "not interested", "going with", "too expensive", "shutting down"]
        medium = ["concern", "worry", "not sure", "compare", "evaluate"]
        if any(k in t for k in high):
            return "high", 0.75
        if any(k in t for k in medium):
            return "medium", 0.45
        return "low", 0.15

    def _infer_objections(self, text: str) -> List[str]:
        obj = []
        triggers = ["too expensive", "not a priority", "already use", "doesn't fit",
                    "need to think", "timing isn't right", "not enough budget"]
        t = text.lower()
        for trigger in triggers:
            if trigger in t:
                obj.append(trigger.capitalize())
        return obj

    def _infer_signals(self, text: str) -> List[str]:
        sigs = []
        triggers = ["next steps", "send proposal", "schedule demo", "move forward",
                    "sign up", "get started", "let's do it", "introduce to team"]
        t = text.lower()
        for trigger in triggers:
            if trigger in t:
                sigs.append(trigger.capitalize())
        return sigs
