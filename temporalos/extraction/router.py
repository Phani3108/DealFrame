"""LLM-powered extraction router — replaces rule-based extractors.

Routes extraction to the configured LLM (OpenAI / Anthropic / Ollama / mock)
with structured JSON output, Pydantic validation, and automatic fallback.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from ..core.types import AlignedSegment, ExtractionResult
from ..llm.router import get_llm, BaseLLMProvider
from .base import BaseExtractionModel

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM = """\
You are a video intelligence analyst. Given a transcript segment from a recorded \
call or meeting, extract structured decision intelligence.

Rules:
- Be precise, evidence-based. Only include objections and signals clearly stated.
- topic: one of pricing|features|competition|timeline|security|onboarding|support|legal|other
- sentiment: positive|neutral|negative|hesitant
- risk: low|medium|high
- risk_score: 0.0 to 1.0
- objections: array of verbatim or close-paraphrase objections
- decision_signals: array of buying intent or next-step signals
- confidence: your confidence in the extraction (0.0 to 1.0)

Respond ONLY with valid JSON. No markdown fences, no commentary.

Here are examples:

Example 1:
Transcript: "That's quite a bit more than what we're paying for our current solution. We'd need to see at least a 20% discount to make this work."
Output: {"topic":"pricing","sentiment":"negative","risk":"high","risk_score":0.75,"objections":["more than current solution","need 20% discount"],"decision_signals":[],"confidence":0.9}

Example 2:
Transcript: "I love the integration capabilities. Can you send over a proposal? I'd like to get this in front of my VP by next Friday."
Output: {"topic":"features","sentiment":"positive","risk":"low","risk_score":0.15,"objections":[],"decision_signals":["send proposal","get in front of VP by Friday"],"confidence":0.92}

Example 3:
Transcript: "We're also evaluating Gong and Chorus. What makes you different? Our security team has some concerns about data residency."
Output: {"topic":"competition","sentiment":"hesitant","risk":"medium","risk_score":0.55,"objections":["evaluating competitors","data residency concerns"],"decision_signals":[],"confidence":0.85}\
"""

EXTRACTION_PROMPT = """\
Timestamp: {timestamp}

Transcript:
{transcript}

Extract structured intelligence as JSON with fields:
topic, sentiment, risk, risk_score, objections, decision_signals, confidence\
"""


class LLMExtractionRouter(BaseExtractionModel):
    """Routes extraction to the active LLM provider with validation + fallback."""
    name = "llm_router"

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self._provider = provider

    def _get_provider(self) -> BaseLLMProvider:
        return self._provider or get_llm()

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        """Sync wrapper for async extraction."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self._extract_async(segment)).result()
        return asyncio.run(self._extract_async(segment))

    async def _extract_async(self, segment: AlignedSegment) -> ExtractionResult:
        llm = self._get_provider()
        transcript = segment.transcript or "(no speech)"
        prompt = EXTRACTION_PROMPT.format(
            timestamp=segment.timestamp_str,
            transcript=transcript,
        )
        t0 = time.monotonic()
        try:
            data = await llm.complete_json(
                prompt=prompt,
                system=EXTRACTION_SYSTEM,
                temperature=0.0,
                max_tokens=512,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            return self._parse_result(data, llm.name, latency_ms)
        except Exception as e:
            logger.warning("LLM extraction failed (%s), using fallback: %s", llm.name, e)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return self._fallback_extract(segment, latency_ms)

    def _parse_result(self, data: Dict[str, Any], model: str, latency_ms: int) -> ExtractionResult:
        return ExtractionResult(
            topic=str(data.get("topic", "other"))[:50],
            sentiment=str(data.get("sentiment", "neutral")),
            risk=str(data.get("risk", "low")),
            risk_score=max(0.0, min(1.0, float(data.get("risk_score", 0.0)))),
            objections=list(data.get("objections", []))[:10],
            decision_signals=list(data.get("decision_signals", []))[:10],
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            model_name=f"llm_{model}",
            latency_ms=latency_ms,
        )

    def _fallback_extract(self, segment: AlignedSegment, latency_ms: int) -> ExtractionResult:
        """Rule-based fallback when LLM fails."""
        text = (segment.transcript or "").lower()

        # Topic detection with weighted matching
        topic_keywords = {
            "pricing": ["price", "cost", "budget", "expensive", "cheap", "discount", "dollars", "per month", "rate"],
            "features": ["feature", "integration", "capability", "functionality", "workflow", "dashboard"],
            "competition": ["competitor", "alternative", "gong", "chorus", "compared to", "versus", "switch from"],
            "timeline": ["timeline", "when", "deadline", "quarter", "by next", "this month", "urgent"],
            "security": ["security", "compliance", "soc2", "gdpr", "encryption", "audit", "hipaa"],
            "onboarding": ["onboard", "implement", "setup", "migration", "getting started", "rollout"],
            "support": ["support", "help desk", "SLA", "response time", "customer service"],
            "legal": ["contract", "terms", "liability", "renewal", "clause", "agreement"],
        }
        topic = "other"
        max_hits = 0
        for t, keywords in topic_keywords.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > max_hits:
                max_hits = hits
                topic = t

        # Objection detection
        risk_score = 0.1
        objections = []
        objection_phrases = [
            "too expensive", "over budget", "not sure", "concerned about",
            "don't think", "might cancel", "not convinced", "hesitant",
            "already using", "no budget", "can't justify", "pushback",
            "not a priority", "too complex", "worried about",
        ]
        for phrase in objection_phrases:
            if phrase in text:
                objections.append(phrase)
                risk_score = min(risk_score + 0.15, 1.0)

        # Decision signal detection
        signals = []
        signal_phrases = [
            "next steps", "move forward", "send proposal", "schedule a demo",
            "bring in my manager", "looks great", "interested", "let's do it",
            "sign the contract", "get started", "when can we",
        ]
        for phrase in signal_phrases:
            if phrase in text:
                signals.append(phrase)
                risk_score = max(risk_score - 0.1, 0.0)

        # Sentiment
        neg_words = sum(1 for w in ["no", "not", "can't", "won't", "never", "expensive", "concerned"] if w in text)
        pos_words = sum(1 for w in ["great", "love", "excellent", "perfect", "excited", "interested"] if w in text)
        if neg_words > pos_words + 1:
            sentiment = "negative"
        elif pos_words > neg_words + 1:
            sentiment = "positive"
        elif neg_words > 0 and pos_words > 0:
            sentiment = "hesitant"
        else:
            sentiment = "neutral"

        risk = "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low"

        return ExtractionResult(
            topic=topic, sentiment=sentiment, risk=risk,
            risk_score=round(risk_score, 2), objections=objections, decision_signals=signals,
            confidence=0.35, model_name="fallback_rules", latency_ms=latency_ms,
        )


# Singleton
_router: Optional[LLMExtractionRouter] = None


def get_extraction_router() -> LLMExtractionRouter:
    global _router
    if _router is None:
        _router = LLMExtractionRouter()
    return _router
