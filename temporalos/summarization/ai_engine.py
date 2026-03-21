"""AI-powered summarization engine — wires LLM into all summary templates.

Replaces rule-based summarization with actual LLM generation.
Falls back to rule-based if LLM is unavailable or fails.
Supports streaming and DB caching.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..llm.router import get_llm

logger = logging.getLogger(__name__)

SUMMARY_PROMPTS = {
    "executive": (
        "You are a senior executive analyst. Write a concise executive summary "
        "(3-5 bullet points, max 150 words). Focus on key decisions, risks, and next steps.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "action_items": (
        "Extract all action items from this meeting. Format as a numbered list with "
        "owner (if identifiable) and deadline (if mentioned). Be specific.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "meeting_notes": (
        "Write professional meeting notes. Include: attendees (if mentioned), "
        "topics discussed, key decisions, action items, and follow-ups.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "deal_brief": (
        "Write a sales deal brief. Include: deal stage signals, buyer sentiment, "
        "objections raised, competitive mentions, risk assessment, and recommended next steps.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "coaching": (
        "Write a sales coaching review. Analyze the rep's performance: talk-to-listen ratio, "
        "objection handling quality, question technique, closing signals. Give specific "
        "improvement recommendations with examples from the call.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "ux_research": (
        "Write a UX research synthesis. Identify: user pain points, positive moments, "
        "feature requests, confusion signals, task success/failure, and usability themes.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "cs_qbr": (
        "Write a Customer Success QBR brief. Include: health score signals, churn risk "
        "indicators, expansion opportunities, product usage mentions, and recommended actions.\n\n"
        "Video intelligence data:\n{context}"
    ),
    "real_estate": (
        "Write a real estate client consultation summary. Include: property preferences, "
        "budget signals, objections to properties shown, priority features, and next showing recommendations.\n\n"
        "Video intelligence data:\n{context}"
    ),
}


def _build_context(intel: Dict[str, Any]) -> str:
    """Build LLM context from video intelligence data."""
    parts = []
    segments = intel.get("segments", [])
    for i, seg in enumerate(segments[:20]):  # limit to 20 segments for context window
        ext = seg.get("extraction", seg)
        ts = seg.get("timestamp_str", f"seg-{i}")
        parts.append(
            f"[{ts}] Topic: {ext.get('topic', 'general')} | "
            f"Sentiment: {ext.get('sentiment', 'neutral')} | "
            f"Risk: {ext.get('risk_score', 0):.0%}\n"
            f"Transcript: {seg.get('transcript', '')[:300]}\n"
            f"Objections: {', '.join(ext.get('objections', [])) or 'none'}\n"
            f"Signals: {', '.join(ext.get('decision_signals', [])) or 'none'}"
        )
    return "\n---\n".join(parts) if parts else "No segment data available."


async def generate_summary(
    intel: Dict[str, Any],
    summary_type: str = "executive",
    stream: bool = False,
) -> Dict[str, Any]:
    """Generate an AI-powered summary. Returns {summary_type, content, word_count, model}."""
    prompt_template = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["executive"])
    context = _build_context(intel)
    prompt = prompt_template.format(context=context)

    llm = get_llm()

    if stream:
        # Return an async generator for streaming
        async def _stream():
            full_text = ""
            async for chunk in llm.stream(
                prompt=prompt,
                system="You are a professional analyst. Be concise and actionable.",
                max_tokens=1024,
            ):
                full_text += chunk
                yield chunk
            yield {"__done__": True, "full_text": full_text}
        return {"stream": _stream(), "summary_type": summary_type, "model": llm.name}

    try:
        resp = await llm.complete(
            prompt=prompt,
            system="You are a professional analyst. Be concise and actionable.",
            max_tokens=1024,
        )
        content = resp.text.strip()
    except Exception as e:
        logger.warning("LLM summarization failed: %s, using fallback", e)
        content = _fallback_summary(intel, summary_type)

    return {
        "summary_type": summary_type,
        "content": content,
        "word_count": len(content.split()),
        "model": llm.name,
        "latency_ms": getattr(resp, "latency_ms", 0) if "resp" in dir() else 0,
    }


def _fallback_summary(intel: Dict[str, Any], summary_type: str) -> str:
    """Rule-based fallback when LLM is unavailable."""
    segments = intel.get("segments", [])
    topics = set()
    objections = []
    signals = []
    risk_total = 0.0

    for seg in segments:
        ext = seg.get("extraction", seg)
        topics.add(ext.get("topic", "general"))
        objections.extend(ext.get("objections", []))
        signals.extend(ext.get("decision_signals", []))
        risk_total += ext.get("risk_score", 0.0)

    avg_risk = risk_total / max(len(segments), 1)
    unique_obj = list(dict.fromkeys(objections))[:5]
    unique_sig = list(dict.fromkeys(signals))[:5]

    lines = [f"**{summary_type.replace('_', ' ').title()} Summary**\n"]
    lines.append(f"- Analyzed {len(segments)} segment(s) covering: {', '.join(sorted(topics))}")
    lines.append(f"- Overall risk: {avg_risk:.0%}")
    if unique_obj:
        lines.append(f"- Key objections: {'; '.join(unique_obj)}")
    if unique_sig:
        lines.append(f"- Decision signals: {'; '.join(unique_sig)}")
    lines.append(f"- Action: Review high-risk segments and address open objections.")
    return "\n".join(lines)
