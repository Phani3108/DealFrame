"""Meeting Prep with LLM context — AI-generated prep briefs.

Wraps MeetingPrepAgent's data aggregation with an LLM narrative layer.
Generates structured brief with talking points, watch-outs, recommended approach.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .meeting_prep import MeetingBrief, MeetingPrepAgent, get_meeting_prep_agent
from ..llm.router import get_llm

logger = logging.getLogger(__name__)

PREP_SYSTEM = """\
You are a sales strategist preparing a rep for their next call. \
Based on the account history data, generate a concise prep brief (200 words max) with:
1. Key context: what happened in past calls
2. Talking points: what to bring up and why
3. Watch-outs: objections to expect, risks to address
4. Recommended approach: open/close strategy for this call
Be specific, citing data when available.\
"""

PREP_PROMPT = """\
Company: {company}
Contact: {contact}
Prior calls: {prior_calls}
Risk trajectory: {risk_trajectory} (last score: {risk_pct}%)

Open objections: {objections}
Recurring topics: {topics}
Open action items: {action_items}

Data-driven talking points:
{talking_points}

Data-driven watch-outs:
{watch_outs}

Generate a prep brief for the upcoming call.\
"""


async def generate_ai_brief(
    company: str,
    contact: str = "",
    agent: Optional[MeetingPrepAgent] = None,
) -> Dict[str, Any]:
    """Generate an AI-enhanced meeting prep brief."""
    prep = agent or get_meeting_prep_agent()
    brief = prep.generate_brief(company, contact)

    result = brief.to_dict()

    prompt = PREP_PROMPT.format(
        company=brief.company,
        contact=brief.contact,
        prior_calls=brief.prior_calls,
        risk_trajectory=brief.risk_trajectory,
        risk_pct=round(brief.last_risk_score * 100),
        objections="; ".join(brief.open_objections) or "none",
        topics="; ".join(brief.recurring_topics) or "none",
        action_items="; ".join(brief.open_action_items) or "none",
        talking_points="\n".join(f"- {tp}" for tp in brief.talking_points),
        watch_outs="\n".join(f"- {w}" for w in brief.watch_outs),
    )

    llm = get_llm()
    try:
        resp = await llm.complete(
            prompt=prompt, system=PREP_SYSTEM,
            temperature=0.2, max_tokens=512,
        )
        result["ai_brief"] = resp.text.strip()
        result["brief_model"] = resp.model
    except Exception as e:
        logger.warning("LLM meeting prep failed: %s", e)
        result["ai_brief"] = _fallback_brief(brief)
        result["brief_model"] = "fallback"

    return result


def _fallback_brief(brief: MeetingBrief) -> str:
    """Plain-text brief when LLM is unavailable."""
    parts = [f"Preparing for call with {brief.company}."]
    if brief.prior_calls:
        parts.append(f"You have {brief.prior_calls} prior call(s) on record.")
    if brief.risk_trajectory != "new":
        parts.append(f"Risk is {brief.risk_trajectory} at {round(brief.last_risk_score * 100)}%.")
    if brief.open_objections:
        parts.append(f"Watch for: {'; '.join(brief.open_objections[:3])}.")
    if brief.talking_points:
        parts.append(f"Key topics: {'; '.join(brief.talking_points[:2])}.")
    return " ".join(parts)
