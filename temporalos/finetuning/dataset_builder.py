"""
Fine-tuning dataset builder — Phase 4.

Converts ExtractionResult + AlignedSegment pairs into LoRA training examples
using the same instruction format as the production extraction adapters, ensuring
the fine-tuned model can serve as a drop-in replacement.

Output format (JSONL, one record per line):
  {
    "id": "<uuid>",
    "instruction": "<system prompt>",
    "input": "<segment context>",
    "output": "<JSON extraction>",
    "metadata": {"model_source": "gpt4o", "timestamp_ms": 4000, ...}
  }
"""

from __future__ import annotations

import json
import random
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# Re-use the same system prompt as the production adapters so training data
# distribution matches inference distribution exactly.
SYSTEM_PROMPT = (
    "You are a sales intelligence analyst. Given a segment from a sales call "
    "(optional screenshot + transcript), extract structured decision intelligence. "
    "Be precise and evidence-based. Only include objections and decision signals "
    "that are clearly stated or strongly implied in the provided content. "
    "Respond ONLY with valid JSON — no prose, no markdown fences."
)

INPUT_TEMPLATE = """\
Timestamp: {timestamp}

Transcript:
{transcript}

Visual context: {visual_context}
"""


@dataclass
class TrainingExample:
    """A single fine-tuning training example."""

    id: str
    instruction: str
    input: str
    output: str  # JSON string
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingExample":
        return cls(**d)


@dataclass
class DatasetSplit:
    train: list[TrainingExample]
    val: list[TrainingExample]

    def __len__(self) -> int:
        return len(self.train) + len(self.val)


class DatasetBuilder:
    """
    Builds LoRA training datasets from duck-typed extraction objects.

    Each object must expose:
      .topic, .sentiment, .risk, .risk_score,
      .objections, .decision_signals, .confidence,
      .model_name (str, used in metadata)

    Optionally, a companion segment object (with .transcript and .timestamp_ms)
    may be provided to populate the input context.
    """

    def __init__(self) -> None:
        self._examples: list[TrainingExample] = []

    # ── Building ─────────────────────────────────────────────────────────────

    def add_example(
        self,
        extraction: Any,
        segment: Any | None = None,
        visual_context: str = "No visual context available.",
    ) -> TrainingExample:
        """
        Create and store one training example from an extraction result.

        Parameters
        ----------
        extraction : duck-typed ExtractionResult (or ORM Extraction)
        segment    : optional duck-typed AlignedSegment (or ORM Segment)
        visual_context : free-text description of the frame (from vision model)
        """
        timestamp = "00:00"
        transcript = ""

        if segment is not None:
            ts_ms = getattr(segment, "timestamp_ms", 0) or 0
            timestamp = _ms_to_str(ts_ms)
            transcript = (
                getattr(segment, "transcript", None)
                or " ".join(
                    getattr(w, "text", "") for w in getattr(segment, "words", [])
                )
            )

        input_text = INPUT_TEMPLATE.format(
            timestamp=timestamp,
            transcript=transcript or "(no transcript)",
            visual_context=visual_context,
        )

        output_payload = {
            "topic": getattr(extraction, "topic", "other"),
            "sentiment": getattr(extraction, "sentiment", "neutral"),
            "risk": getattr(extraction, "risk", "low"),
            "risk_score": float(getattr(extraction, "risk_score", 0.0)),
            "objections": list(getattr(extraction, "objections", []) or []),
            "decision_signals": list(getattr(extraction, "decision_signals", []) or []),
            "confidence": float(getattr(extraction, "confidence", 0.0)),
        }

        example = TrainingExample(
            id=str(uuid.uuid4()),
            instruction=SYSTEM_PROMPT,
            input=input_text,
            output=json.dumps(output_payload),
            metadata={
                "model_source": getattr(extraction, "model_name", "unknown"),
                "timestamp_ms": getattr(segment, "timestamp_ms", 0) if segment else 0,
            },
        )
        self._examples.append(example)
        return example

    # ── Bulk helpers ──────────────────────────────────────────────────────────

    def add_batch(
        self,
        pairs: list[tuple[Any, Any | None]],
        visual_context: str = "No visual context available.",
    ) -> list[TrainingExample]:
        """Add a list of (extraction, segment) pairs at once."""
        return [self.add_example(ext, seg, visual_context) for ext, seg in pairs]

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._examples)

    def class_distribution(self) -> dict[str, dict[str, int]]:
        """Return count of each class for topic, sentiment, risk, risk_bucket."""
        dist: dict[str, dict[str, int]] = {
            "topic": {}, "sentiment": {}, "risk": {}
        }
        for ex in self._examples:
            payload = json.loads(ex.output)
            for field_name in ("topic", "sentiment", "risk"):
                val = payload.get(field_name, "unknown")
                dist[field_name][val] = dist[field_name].get(val, 0) + 1
        return dist

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_jsonl(self, path: str | Path) -> Path:
        """Write all examples to a JSONL file. Creates parent dirs if needed."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as fh:
            for ex in self._examples:
                fh.write(json.dumps(ex.to_dict()) + "\n")
        return p

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "DatasetBuilder":
        """Load examples from a JSONL file."""
        builder = cls()
        with Path(path).open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    builder._examples.append(
                        TrainingExample.from_dict(json.loads(line))
                    )
        return builder

    # ── Splitting ────────────────────────────────────────────────────────────

    def split(self, train_ratio: float = 0.8, seed: int = 42) -> DatasetSplit:
        """Stratified split by risk bucket."""
        rng = random.Random(seed)
        examples = list(self._examples)
        rng.shuffle(examples)
        n_train = max(1, int(len(examples) * train_ratio))
        return DatasetSplit(train=examples[:n_train], val=examples[n_train:])

    def __len__(self) -> int:
        return len(self._examples)


# ── DB-backed loader ──────────────────────────────────────────────────────────

async def build_dataset_from_db(session: Any, min_confidence: float = 0.7) -> DatasetBuilder:
    """
    Query the DB for all high-confidence extractions and build a training dataset.
    Requires an active SQLAlchemy AsyncSession.
    """
    from sqlalchemy import select

    from ..db.models import Extraction, Segment

    stmt = (
        select(Extraction, Segment)
        .join(Segment, Extraction.segment_id == Segment.id)
        .where(Extraction.confidence >= min_confidence)
    )
    result = await session.execute(stmt)
    rows = result.all()

    builder = DatasetBuilder()
    for extraction, segment in rows:
        builder.add_example(extraction, segment)
    return builder


# ── Utilities ─────────────────────────────────────────────────────────────────

def _ms_to_str(ms: int) -> str:
    seconds = ms // 1000
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"
