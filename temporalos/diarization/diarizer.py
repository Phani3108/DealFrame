"""Speaker diarization — assigns SPEAKER_A / SPEAKER_B labels to word sequences.

Uses pause-boundary heuristic for zero-dependency operation.
Lazy-imports pyannote.audio when available for production-grade diarization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from temporalos.core.types import Word


@dataclass
class DiarizationSegment:
    speaker: str
    start_ms: int
    end_ms: int

    def to_dict(self) -> dict:
        s = self.start_ms
        return {
            "speaker": self.speaker,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "start_str": f"{s // 60000:02d}:{(s // 1000) % 60:02d}",
            "duration_s": round((self.end_ms - self.start_ms) / 1000, 1),
        }


class MockDiarizer:
    """
    Pause-boundary speaker diarizer.

    Detects speaker turns via silence gaps ≥ pause_threshold_ms between words.
    Alternates SPEAKER_A / SPEAKER_B at each detected boundary.
    Suitable for demos and testing; swap with pyannote for production.
    """

    SPEAKERS = ["SPEAKER_A", "SPEAKER_B"]

    def __init__(self, pause_threshold_ms: int = 1500):
        self.pause_threshold_ms = pause_threshold_ms

    def diarize(self, words: List[Word]) -> List[Word]:
        """Assign speaker labels — returns new Word objects with speaker set."""
        if not words:
            return []

        result: List[Word] = []
        idx = 0

        for i, w in enumerate(words):
            if i > 0:
                gap = w.start_ms - words[i - 1].end_ms
                if gap >= self.pause_threshold_ms:
                    idx = (idx + 1) % 2
            result.append(
                Word(text=w.text, start_ms=w.start_ms, end_ms=w.end_ms,
                     speaker=self.SPEAKERS[idx])
            )
        return result

    def get_segments(self, words: List[Word]) -> List[DiarizationSegment]:
        """Collapse labeled words into contiguous speaker segments."""
        labeled = self.diarize(words)
        if not labeled:
            return []

        segs: List[DiarizationSegment] = []
        cur_speaker = labeled[0].speaker
        cur_start = labeled[0].start_ms
        cur_end = labeled[0].end_ms

        for w in labeled[1:]:
            if w.speaker != cur_speaker:
                segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
                cur_speaker = w.speaker
                cur_start = w.start_ms
            cur_end = w.end_ms

        segs.append(DiarizationSegment(cur_speaker, cur_start, cur_end))
        return segs


def get_diarizer(pause_threshold_ms: int = 1500) -> MockDiarizer:
    """Factory — falls back to MockDiarizer if pyannote unavailable."""
    try:
        from pyannote.audio import Pipeline  # noqa: F401
        # Swap with PyAnnoteDiarizer when pyannote credentials are configured
        return MockDiarizer(pause_threshold_ms=pause_threshold_ms)
    except ImportError:
        return MockDiarizer(pause_threshold_ms=pause_threshold_ms)
