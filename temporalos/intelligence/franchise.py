"""Franchise Mode — auto-detect content vertical and apply schema.

Classifies video content as: sales_call, ux_research, customer_success,
legal_deposition, real_estate, medical_consultation, hr_interview, general.
Uses keyword heuristics + optional LLM classification.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Keyword markers per vertical
VERTICAL_KEYWORDS: Dict[str, List[str]] = {
    "sales_call": [
        "pricing", "discount", "proposal", "budget", "contract", "competitor",
        "deal", "close", "pipeline", "quota", "commission", "roi", "demo",
        "objection", "decision maker", "stakeholder", "procurement",
    ],
    "ux_research": [
        "usability", "user experience", "pain point", "workflow", "prototype",
        "wireframe", "navigation", "interface", "task", "participant",
        "user test", "screen share", "think aloud", "A/B test",
    ],
    "customer_success": [
        "churn", "renewal", "health score", "adoption", "onboarding",
        "expansion", "upsell", "NPS", "satisfaction", "support ticket",
        "QBR", "quarterly review", "account health",
    ],
    "legal_deposition": [
        "deposition", "testimony", "counsel", "attorney", "exhibit",
        "objection sustained", "objection overruled", "witness", "sworn",
        "court", "plaintiff", "defendant", "stipulate",
    ],
    "real_estate": [
        "property", "listing", "mortgage", "square feet", "bedrooms",
        "showing", "open house", "closing costs", "appraisal",
        "neighborhood", "school district", "inspection",
    ],
    "medical_consultation": [
        "patient", "diagnosis", "symptoms", "prescription", "treatment",
        "follow-up", "vitals", "blood pressure", "medication", "referral",
    ],
    "hr_interview": [
        "candidate", "resume", "experience", "strengths", "weaknesses",
        "team fit", "salary expectations", "notice period", "background check",
    ],
    "procurement": [
        "supplier", "vendor", "rfp", "sourcing", "procurement",
        "tender", "bid", "contract terms", "payment terms", "net 30",
        "net 60", "sla", "lead time", "per unit", "volume discount",
        "concession", "compliance", "audit", "total cost",
        "maverick spend", "category management", "spend analysis",
    ],
}

# Schema fields per vertical
VERTICAL_SCHEMAS: Dict[str, Dict[str, str]] = {
    "sales_call": {
        "deal_stage": "string", "buyer_sentiment": "string",
        "competition_mentioned": "list[str]", "pricing_discussed": "bool",
        "next_steps": "list[str]", "close_probability": "float",
    },
    "ux_research": {
        "pain_points": "list[str]", "feature_requests": "list[str]",
        "task_success": "bool", "confusion_moments": "list[str]",
        "satisfaction_score": "float", "usability_issues": "list[str]",
    },
    "customer_success": {
        "health_score": "float", "churn_risk": "string",
        "expansion_signals": "list[str]", "support_issues": "list[str]",
        "adoption_metrics": "dict", "renewal_status": "string",
    },
    "real_estate": {
        "property_type": "string", "budget_range": "string",
        "preferences": "list[str]", "objections_to_property": "list[str]",
        "showing_feedback": "string", "next_showing": "string",
    },
    "procurement": {
        "negotiation_stage": "string", "commitment_strength": "string",
        "pricing_signals": "list[str]", "concessions_offered": "list[str]",
        "supplier_risk_score": "float", "clause_objections": "list[str]",
        "compliance_mentions": "list[str]", "sla_commitments_discussed": "bool",
    },
    "general": {
        "topic": "string", "sentiment": "string",
        "key_points": "list[str]", "action_items": "list[str]",
    },
}


def classify_vertical(intel: Dict[str, Any]) -> Tuple[str, float, Dict[str, float]]:
    """Classify video content into a vertical.

    Returns: (vertical_name, confidence, all_scores)
    """
    # Gather all text
    text_parts = []
    for seg in intel.get("segments", []):
        ext = seg.get("extraction", seg)
        text_parts.append(seg.get("transcript", ""))
        text_parts.append(ext.get("topic", ""))
        text_parts.extend(ext.get("objections", []))
        text_parts.extend(ext.get("decision_signals", []))
    combined = " ".join(text_parts).lower()

    # Score each vertical
    scores: Dict[str, float] = {}
    for vertical, keywords in VERTICAL_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        scores[vertical] = hits / len(keywords) if keywords else 0

    # Determine winner
    if not scores:
        return "general", 0.0, {}

    best = max(scores, key=lambda k: scores[k])
    confidence = scores[best]

    # Require minimum threshold
    if confidence < 0.1:
        return "general", confidence, scores

    return best, round(confidence, 3), {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])}


def get_schema_for_vertical(vertical: str) -> Dict[str, str]:
    """Get the extraction schema for a vertical."""
    return VERTICAL_SCHEMAS.get(vertical, VERTICAL_SCHEMAS["general"])


def auto_classify_and_extract(intel: Dict[str, Any]) -> Dict[str, Any]:
    """Classify vertical and return enriched intel with schema metadata."""
    vertical, confidence, scores = classify_vertical(intel)
    schema = get_schema_for_vertical(vertical)

    return {
        "detected_vertical": vertical,
        "vertical_confidence": confidence,
        "vertical_scores": scores,
        "schema": schema,
        "intelligence": intel,
    }
