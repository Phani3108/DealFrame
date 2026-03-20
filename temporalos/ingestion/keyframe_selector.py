"""Deduplicate visually similar frames using a simple perceptual hash.

Reads the first N bytes of each image file and folds them into a 64-bit
integer via XOR. Hamming distance between hashes approximates visual
similarity well enough for deduplication without requiring PIL/numpy.
"""

from __future__ import annotations

from ..core.types import Frame

_HASH_BYTES = 512  # bytes to sample from each image for the hash


def _file_hash(image_path: str) -> int:
    """Compute a lightweight hash from file bytes (no image decoding needed)."""
    try:
        with open(image_path, "rb") as f:
            data = f.read(_HASH_BYTES)
        h = 0
        for i, b in enumerate(data):
            h ^= b << (i % 64)
        return h
    except OSError:
        return 0


def _hamming(a: int, b: int) -> int:
    """Count differing bits between two 64-bit integers."""
    return bin(a ^ b).count("1")


class KeyframeSelector:
    """
    Removes visually redundant frames from a sequence using perceptual hashing.

    A frame is kept if its hash differs from the most recently kept frame
    by more than `similarity_threshold` bits. Lower threshold retains fewer
    frames; higher threshold keeps more.
    """

    def __init__(self, similarity_threshold: int = 5) -> None:
        self._threshold = similarity_threshold

    def select(self, frames: list[Frame]) -> list[Frame]:
        """Return a deduplicated list of keyframes."""
        if not frames:
            return []

        selected: list[Frame] = []
        last_hash: int | None = None

        for frame in frames:
            h = _file_hash(frame.path)
            if last_hash is None or _hamming(h, last_hash) > self._threshold:
                selected.append(frame)
                last_hash = h

        return selected if selected else frames[:1]
