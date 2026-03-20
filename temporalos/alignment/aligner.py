"""Temporal alignment — join video frames with transcript words by timestamp."""

from ..core.types import AlignedSegment, Frame, Word
from ..observability.telemetry import get_tracer


def align(frames: list[Frame], words: list[Word]) -> list[AlignedSegment]:
    """
    Nearest-neighbour temporal alignment.

    For each frame at timestamp T, collect all words whose start_ms falls in
    the window [T, T_next).  This produces one AlignedSegment per frame,
    each containing the words spoken while that frame was on screen.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("alignment.align") as span:
        span.set_attribute("alignment.frame_count", len(frames))
        span.set_attribute("alignment.word_count", len(words))

        if not frames:
            return []

        segments: list[AlignedSegment] = []

        for i, frame in enumerate(frames):
            window_start = frame.timestamp_ms
            # Window ends at the next frame's timestamp (or +5 s for the last frame)
            window_end = (
                frames[i + 1].timestamp_ms if i + 1 < len(frames) else frame.timestamp_ms + 5000
            )

            frame_words = [
                w for w in words if window_start <= w.start_ms < window_end
            ]
            segments.append(
                AlignedSegment(
                    timestamp_ms=frame.timestamp_ms,
                    frame=frame,
                    words=frame_words,
                )
            )

        non_empty = sum(1 for s in segments if s.words)
        span.set_attribute("alignment.non_empty_segments", non_empty)
        return segments
