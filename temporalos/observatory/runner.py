"""
Observatory runner — Phase 2: Comparative Model Observatory.

Runs the same video segment through multiple vision + extraction model adapters
in parallel, then computes agreement scores and surfaces disagreements for
evaluation and benchmarking.

Key classes (to be implemented):
  - ObservatoryRunner  — orchestrates parallel multi-model inference
  - ModelRun           — result from one model on one segment
  - ComparisonReport   — pairwise agreement metrics across models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import AlignedSegment, ExtractionResult
    from ..vision.base import BaseVisionModel, FrameAnalysis
    from ..extraction.base import BaseExtractionModel


@dataclass
class ModelRun:
    """Single model result on a single segment — Phase 2 data model."""

    model_name: str
    segment_timestamp_ms: int
    extraction: "ExtractionResult | None" = None
    vision: "FrameAnalysis | None" = None
    error: str | None = None


@dataclass
class ComparisonReport:
    """Pairwise agreement metrics across all registered models — Phase 2 output."""

    model_names: list[str] = field(default_factory=list)
    topic_agreement_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    sentiment_agreement_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    avg_risk_score_per_model: dict[str, float] = field(default_factory=dict)
    disagreement_segments: list[int] = field(default_factory=list)  # timestamp_ms list


class ObservatoryRunner:
    """
    Phase 2 — Comparative Model Observatory.

    Registers vision and extraction model adapters, then runs all of them over
    the same set of segments in parallel (ThreadPoolExecutor), collecting
    ModelRun results for comparison.

    Usage (Phase 2):
        runner = ObservatoryRunner()
        runner.register_extractor(GPT4oExtractionModel.from_settings())
        runner.register_extractor(ClaudeExtractionModel.from_settings())
        runner.register_extractor(QwenVLExtractionModel.from_settings())

        runs = runner.run(segments)
        report = runner.compare(runs)
    """

    def __init__(self) -> None:
        self._extractors: list["BaseExtractionModel"] = []
        self._vision_models: list["BaseVisionModel"] = []

    def register_extractor(self, model: "BaseExtractionModel") -> None:
        self._extractors.append(model)

    def register_vision_model(self, model: "BaseVisionModel") -> None:
        self._vision_models.append(model)

    # Phase 2 TODO: implement run() and compare()
    def run(self, segments: "list[AlignedSegment]") -> list[ModelRun]:
        raise NotImplementedError("ObservatoryRunner.run() — Phase 2")

    def compare(self, runs: list[ModelRun]) -> ComparisonReport:
        raise NotImplementedError("ObservatoryRunner.compare() — Phase 2")
