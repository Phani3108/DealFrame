"""Abstract base class for all extraction model adapters."""

from abc import ABC, abstractmethod

from ..core.types import AlignedSegment, ExtractionResult


class BaseExtractionModel(ABC):
    """
    Contract that every extraction adapter must satisfy.

    Implementations live in temporalos/extraction/models/:
      - gpt4o.py       — GPT-4o with vision (Phase 1)
      - claude.py      — Claude Sonnet Vision (Phase 2)
      - finetuned.py   — Local fine-tuned model (Phase 4/5)
    """

    name: str = "base"

    @abstractmethod
    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        """Extract structured intelligence from a single aligned segment."""
        ...

    def extract_batch(self, segments: list[AlignedSegment]) -> list[ExtractionResult]:
        """Default: sequential extraction. Override for true batching."""
        return [self.extract(s) for s in segments]
