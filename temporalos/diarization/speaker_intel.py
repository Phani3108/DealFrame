"""Per-speaker analytics computed from diarized word sequences."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from temporalos.core.types import Word

FILLER_WORDS = frozenset({
    "um", "uh", "like", "basically", "literally", "actually",
    "right", "okay", "so", "yeah", "yep",
})


@dataclass
class SpeakerStats:
    speaker: str
    word_count: int = 0
    total_ms: int = 0
    question_count: int = 0
    filler_count: int = 0
    interruptions: int = 0

    @property
    def words_per_minute(self) -> float:
        if self.total_ms < 100:
            return 0.0
        return round(self.word_count / (self.total_ms / 60_000), 1)

    @property
    def filler_rate(self) -> float:
        if self.word_count == 0:
            return 0.0
        return round(self.filler_count / self.word_count, 4)

    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "word_count": self.word_count,
            "total_seconds": round(self.total_ms / 1000, 1),
            "words_per_minute": self.words_per_minute,
            "question_count": self.question_count,
            "filler_rate": self.filler_rate,
            "interruptions": self.interruptions,
        }


@dataclass
class SpeakerIntelligence:
    stats: Dict[str, SpeakerStats] = field(default_factory=dict)

    @property
    def talk_ratio(self) -> Dict[str, float]:
        total = sum(s.total_ms for s in self.stats.values())
        if total == 0:
            return {k: 0.0 for k in self.stats}
        return {k: round(v.total_ms / total, 3) for k, v in self.stats.items()}

    @property
    def dominant_speaker(self) -> str | None:
        if not self.stats:
            return None
        return max(self.stats, key=lambda k: self.stats[k].total_ms)

    def to_dict(self) -> dict:
        return {
            "speaker_stats": {k: v.to_dict() for k, v in self.stats.items()},
            "talk_ratio": self.talk_ratio,
            "speaker_count": len(self.stats),
            "dominant_speaker": self.dominant_speaker,
        }


def compute_speaker_intelligence(words: List[Word]) -> SpeakerIntelligence:
    """Compute per-speaker stats from a list of (optionally diarized) Words."""
    intel = SpeakerIntelligence()
    prev_speaker: str | None = None

    for w in words:
        speaker = w.speaker or "UNKNOWN"
        if speaker not in intel.stats:
            intel.stats[speaker] = SpeakerStats(speaker=speaker)

        s = intel.stats[speaker]
        s.word_count += 1
        s.total_ms += max(0, w.end_ms - w.start_ms)

        clean = w.text.lower().strip("?.,!;:'\"")
        if w.text.rstrip().endswith("?"):
            s.question_count += 1
        if clean in FILLER_WORDS:
            s.filler_count += 1

        # Interruption: speaker changed with tiny overlap/gap (<300 ms)
        if prev_speaker and prev_speaker != speaker:
            s.interruptions += 1

        prev_speaker = speaker

    return intel
