"""
Local pipeline benchmark — Phase 5.

Measures latency and (when ground truth is available) accuracy comparison
between the local SLM pipeline and API-based pipelines.

Usage:
    runner = BenchmarkRunner()
    local_result = runner.run_local("call.mp4", pipeline)
    api_result = runner.run_api("call.mp4", gpt4o_model)
    comparison = runner.compare(local_result, api_result)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkResult:
    """Timing + extraction outputs from one pipeline run."""

    model_name: str
    video_path: str
    total_latency_ms: int
    stage_latencies_ms: dict[str, int] = field(default_factory=dict)
    extractions: list[dict] = field(default_factory=list)
    extraction_count: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "video_path": self.video_path,
            "total_latency_ms": self.total_latency_ms,
            "stage_latencies_ms": self.stage_latencies_ms,
            "extraction_count": self.extraction_count,
            "error": self.error,
        }


@dataclass
class BenchmarkComparison:
    """Side-by-side comparison of two pipeline runs."""

    local: BenchmarkResult
    api: BenchmarkResult
    latency_ratio: float   # local / api (< 1 = local is faster)
    cost_savings_usd: float  # estimated USD saved by going local

    @property
    def local_is_faster(self) -> bool:
        return self.latency_ratio < 1.0

    def to_dict(self) -> dict:
        return {
            "local": self.local.to_dict(),
            "api": self.api.to_dict(),
            "latency_ratio": round(self.latency_ratio, 3),
            "local_is_faster": self.local_is_faster,
            "cost_savings_usd": round(self.cost_savings_usd, 4),
            "verdict": self._verdict(),
        }

    def _verdict(self) -> str:
        if self.latency_ratio <= 1.5 and self.cost_savings_usd > 0:
            return "local_recommended"
        elif self.latency_ratio <= 3.0:
            return "local_acceptable"
        else:
            return "local_too_slow"


# ── Estimated API costs ────────────────────────────────────────────────────────
# GPT-4o pricing (per 1K tokens, approximate):
_GPT4O_INPUT_PER_K = 0.005
_GPT4O_OUTPUT_PER_K = 0.015
_AVG_TOKENS_PER_SEGMENT = 400  # rough estimate for extraction prompt + output


class BenchmarkRunner:
    """
    Runs the local and API pipelines on the same video and compares results.
    All actual API calls are mocked in tests — this class just orchestrates.
    """

    def run_local(
        self,
        video_path: str,
        pipeline: Any,
        use_vision: bool = False,
    ) -> BenchmarkResult:
        """Run the LocalPipeline and capture timing."""
        start = time.time()
        try:
            result = pipeline.process(video_path, use_vision=use_vision)
            segments = result.video_intelligence.segments or []
            return BenchmarkResult(
                model_name=result.extraction_model,
                video_path=video_path,
                total_latency_ms=result.total_latency_ms,
                stage_latencies_ms=result.stage_latencies_ms,
                extractions=[
                    {
                        "topic": e.topic,
                        "risk": e.risk,
                        "confidence": e.confidence,
                    }
                    for (_, e) in segments
                ],
                extraction_count=len(segments),
            )
        except Exception as exc:
            return BenchmarkResult(
                model_name="local",
                video_path=video_path,
                total_latency_ms=int((time.time() - start) * 1000),
                error=str(exc),
            )

    def run_api(
        self,
        video_path: str,
        model: Any,
        segments: list | None = None,
    ) -> BenchmarkResult:
        """Run the API model and capture timing."""
        start = time.time()
        extractions = []
        try:
            if segments:
                results = model.extract_batch([s for s in segments if s.words])
                extractions = [
                    {"topic": r.topic, "risk": r.risk, "confidence": r.confidence}
                    for r in results
                ]
            total_ms = int((time.time() - start) * 1000)
            return BenchmarkResult(
                model_name=getattr(model, "name", "api"),
                video_path=video_path,
                total_latency_ms=total_ms,
                extraction_count=len(extractions),
                extractions=extractions,
            )
        except Exception as exc:
            return BenchmarkResult(
                model_name=getattr(model, "name", "api"),
                video_path=video_path,
                total_latency_ms=int((time.time() - start) * 1000),
                error=str(exc),
            )

    def compare(
        self,
        local: BenchmarkResult,
        api: BenchmarkResult,
        segments_count: int | None = None,
    ) -> BenchmarkComparison:
        """Compare local and API results, compute cost savings."""
        if api.total_latency_ms == 0:
            ratio = 0.0
        else:
            ratio = local.total_latency_ms / api.total_latency_ms

        n = segments_count or max(local.extraction_count, api.extraction_count, 1)
        api_cost = n * _AVG_TOKENS_PER_SEGMENT * (_GPT4O_INPUT_PER_K + _GPT4O_OUTPUT_PER_K) / 1000
        local_cost = 0.0  # no API cost for local

        return BenchmarkComparison(
            local=local,
            api=api,
            latency_ratio=ratio,
            cost_savings_usd=api_cost - local_cost,
        )
