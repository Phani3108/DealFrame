"""
Vision model adapter interface — Phase 2: Comparative Model Observatory.

Implementations will live in temporalos/vision/models/:
  - gpt4o_vision.py    — GPT-4o Vision
  - claude_vision.py   — Claude Sonnet Vision
  - qwen_vl.py         — Qwen2.5-VL (local, no API call)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..core.types import Frame


@dataclass
class FrameAnalysis:
    """Structured output from a vision model analysing a single frame."""

    frame_type: str  # slide | face | screen | chart | whiteboard | other
    ocr_text: str
    objects: list[str] = field(default_factory=list)
    confidence: float = 0.0
    model_name: str = ""
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "frame_type": self.frame_type,
            "ocr_text": self.ocr_text,
            "objects": self.objects,
            "confidence": self.confidence,
            "model": self.model_name,
            "latency_ms": self.latency_ms,
        }


class BaseVisionModel(ABC):
    """
    Contract every vision model adapter must satisfy.
    Phase 2 will register adapters here for the Observatory runner.
    """

    name: str = "base"

    @abstractmethod
    def analyze_frame(self, frame: Frame) -> FrameAnalysis:
        """Analyse a single video frame and return structured visual intelligence."""
        ...

    def analyze_batch(self, frames: list[Frame]) -> list[FrameAnalysis]:
        """Default: sequential. Override with true batching where the API supports it."""
        return [self.analyze_frame(f) for f in frames]
