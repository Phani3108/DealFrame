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

Respond ONLY with valid JSON. No markdown fences, no commentary.\
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
        topic = "other"
        for kw, t in [("price", "pricing"), ("cost", "pricing"), ("feature", "features"),
                       ("competitor", "competition"), ("timeline", "timeline"),
                       ("security", "security"), ("onboard", "onboarding")]:
            if kw in text:
                topic = t
                break
        risk_score = 0.1
        objections = []
        for phrase in ["too expensive", "not sure", "concerned", "don't think", "cancel"]:
            if phrase in text:
                objections.append(phrase)
                risk_score = min(risk_score + 0.2, 1.0)
        signals = []
        for phrase in ["next steps", "move forward", "send proposal", "schedule"]:
            if phrase in text:
                signals.append(phrase)
        return ExtractionResult(
            topic=topic, sentiment="neutral", risk="medium" if risk_score > 0.3 else "low",
            risk_score=risk_score, objections=objections, decision_signals=signals,
            confidence=0.3, model_name="fallback_rules", latency_ms=latency_ms,
        )


# Singleton
_router: Optional[LLMExtractionRouter] = None


def get_extraction_router() -> LLMExtractionRouter:
    global _router
    if _router is None:
        _router = LLMExtractionRouter()
    return _router
