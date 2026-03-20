"""Heuristic frame-type classification using image statistics.

Classifies each frame into one of:
  SLIDE   — bright, low-contrast (presentation slide)
  SCREEN  — bright, moderate edges (app screen / UI demo)
  CHART   — wide frame, high edge density
  FACE    — tall frame or moderate brightness + high edges
  MIXED   — doesn't clearly fit other categories
  UNKNOWN — PIL unavailable or image unreadable

No vision model required. Uses PIL for pixel statistics + edge detection.
"""

from __future__ import annotations

import enum
from pathlib import Path


class FrameType(str, enum.Enum):
    SLIDE = "slide"
    FACE = "face"
    SCREEN = "screen"
    CHART = "chart"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SlideClassifier:
    """
    Classify a video frame into FrameType using image statistics.

    Heuristics:
      - Mean brightness > 180 AND edge density < 0.15  → SLIDE
      - Mean brightness > 150 AND edge density < 0.30  → SCREEN
      - Edge density > 0.25 AND height > width         → FACE
      - Edge density > 0.25                            → CHART
      - Otherwise                                      → MIXED
    """

    def classify(self, image_path: str) -> FrameType:
        if not Path(image_path).exists():
            return FrameType.UNKNOWN
        try:
            return self._pil_classify(image_path)
        except Exception:
            return FrameType.UNKNOWN

    @staticmethod
    def _pil_classify(image_path: str) -> FrameType:
        try:
            from PIL import Image, ImageFilter  # type: ignore[import]
        except ImportError:
            return FrameType.UNKNOWN

        img = Image.open(image_path).convert("L")  # grayscale
        w, h = img.size
        pixels = list(img.getdata())
        mean_brightness = sum(pixels) / len(pixels)

        edges = img.filter(ImageFilter.FIND_EDGES)
        edge_pixels = list(edges.getdata())
        edge_density = sum(1 for p in edge_pixels if p > 30) / len(edge_pixels)

        if mean_brightness > 180 and edge_density < 0.15:
            return FrameType.SLIDE
        if mean_brightness > 150 and edge_density < 0.30:
            return FrameType.SCREEN
        if edge_density > 0.25:
            return FrameType.FACE if h > w else FrameType.CHART
        return FrameType.MIXED

    def classify_batch(self, image_paths: list[str]) -> list[FrameType]:
        return [self.classify(p) for p in image_paths]
