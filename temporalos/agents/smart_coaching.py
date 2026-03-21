"""Smart Coaching Engine — LLM-powered coaching narratives.

Wraps the existing CoachingEngine (5-dimension scoring) and adds:
  - LLM-generated coaching narrative citing specific call moments
  - Comparison to team benchmarks with actionable advice
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .coaching import CoachingCard, CoachingEngine, get_coaching_engine
from ..llm.router import get_llm

logger = logging.getLogger(__name__)

COACHING_SYSTEM = """\
You are an expert sales coach analyzing rep performance data. \
Generate a personalized coaching brief that:
1. Celebrates strengths with specific examples
2. Identifies 2-3 concrete improvement areas
3. Gives actionable next-call tips
4. References specific call moments (timestamps/topics) when available
Keep it conversational but professional. 200-300 words max.\
"""

COACHING_PROMPT = """\
Rep: {rep_id}
Calls analyzed: {calls_analyzed}
Overall grade: {grade} ({overall_score}/1.0)

Performance dimensions:
{dimensions}

Strengths: {strengths}
Areas to improve: {improvements}

Recent high-risk moments:
{moments}

Generate a coaching narrative for this rep.\
"""


async def generate_coaching_narrative(
    card: CoachingCard,
) -> Dict[str, Any]:
    """Take a scoring-based CoachingCard, add an LLM narrative."""
    dims_text = "\n".join(
        f"- {d.name}: {d.verdict} (score={d.score:.2f}, value={d.value:.3f}, "
        f"benchmark={d.benchmark:.3f}). Tip: {d.tip}"
        for d in card.dimensions
    )
    moments_text = "\n".join(
        f"- [{m.get('job_id', '?')} @ {m.get('timestamp', '?')}] topic: {m.get('topic', '?')}"
        for m in card.example_moments
    ) or "None recorded."

    prompt = COACHING_PROMPT.format(
        rep_id=card.rep_id,
        calls_analyzed=card.calls_analyzed,
        grade=card._grade(),
        overall_score=f"{card.overall_score:.2f}",
        dimensions=dims_text,
        strengths="; ".join(card.strengths),
        improvements="; ".join(card.improvements),
        moments=moments_text,
    )

    llm = get_llm()
    try:
        resp = await llm.complete(
            prompt=prompt, system=COACHING_SYSTEM,
            temperature=0.3, max_tokens=512,
        )
        narrative = resp.text.strip()
        model_name = resp.model
    except Exception as e:
        logger.warning("LLM coaching failed: %s", e)
        narrative = _fallback_narrative(card)
        model_name = "fallback"

    result = card.to_dict()
    result["narrative"] = narrative
    result["narrative_model"] = model_name
    return result


def _fallback_narrative(card: CoachingCard) -> str:
    """Rule-based narrative when LLM is unavailable."""
    parts = [f"{card.rep_id} scored a {card._grade()} across {card.calls_analyzed} call(s)."]
    if card.strengths:
        parts.append(f"Strengths: {', '.join(card.strengths)}.")
    if card.improvements:
        parts.append(f"Focus areas: {'; '.join(card.improvements[:2])}.")
    return " ".join(parts)


async def smart_coaching(
    rep_id: str,
    engine: Optional[CoachingEngine] = None,
) -> Optional[Dict[str, Any]]:
    """Full smart coaching pipeline: score + narrative."""
    eng = engine or get_coaching_engine()
    card = eng.generate_coaching_card(rep_id)
    if card is None:
        return None
    return await generate_coaching_narrative(card)
