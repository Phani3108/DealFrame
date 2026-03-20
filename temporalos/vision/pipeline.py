"""Full vision pipeline: keyframe deduplication → OCR → frame-type classification.

Integrates:
  - KeyframeSelector  (ingestion)
  - SceneDetector     (ingestion)
  - OcrEngine         (vision)
  - SlideClassifier   (vision)

The EnrichedFrame output is designed to slot into AlignedSegment to give the
extraction models visual context (OCR text, frame type, scene boundary flag).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.types import Frame
from ..ingestion.keyframe_selector import KeyframeSelector
from ..ingestion.scene_detector import SceneBoundary, SceneDetector
from .ocr import OcrEngine, OcrResult
from .slide_classifier import FrameType, SlideClassifier


@dataclass
class EnrichedFrame:
    """A video frame annotated with OCR text and visual classification."""

    frame: Frame
    frame_type: FrameType = FrameType.UNKNOWN
    ocr: OcrResult | None = None
    scene_boundary: SceneBoundary | None = None

    @property
    def timestamp_ms(self) -> int:
        return self.frame.timestamp_ms

    @property
    def ocr_text(self) -> str:
        return self.ocr.text if self.ocr else ""

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "timestamp_str": self.frame.timestamp_str,
            "frame_type": self.frame_type.value,
            "ocr_text": self.ocr_text,
            "ocr_confidence": self.ocr.confidence if self.ocr else 0.0,
            "is_scene_boundary": self.scene_boundary is not None,
        }


class VisionPipeline:
    """
    Full vision analysis pipeline for a list of extracted frames.

    Steps:
      1. Deduplicate similar frames with KeyframeSelector
      2. Run OCR on each keyframe
      3. Classify each keyframe's type (slide, screen, face, chart, mixed)
      4. (When video_path provided) Tag scene boundaries from SceneDetector
    """

    def __init__(
        self,
        run_ocr: bool = True,
        run_classification: bool = True,
        dedup_threshold: int = 5,
    ) -> None:
        self._selector = KeyframeSelector(similarity_threshold=dedup_threshold)
        self._ocr = OcrEngine() if run_ocr else None
        self._classifier = SlideClassifier() if run_classification else None
        self._scene_detector = SceneDetector()

    def process(self, frames: list[Frame]) -> list[EnrichedFrame]:
        """Deduplicate, OCR, and classify a list of frames."""
        keyframes = self._selector.select(frames)
        enriched: list[EnrichedFrame] = []

        for frame in keyframes:
            ocr_result = self._ocr.extract(frame.path) if self._ocr else None
            frame_type = (
                self._classifier.classify(frame.path)
                if self._classifier
                else FrameType.UNKNOWN
            )
            enriched.append(EnrichedFrame(frame=frame, frame_type=frame_type, ocr=ocr_result))

        return enriched

    def process_video(self, video_path: str, frames: list[Frame]) -> list[EnrichedFrame]:
        """
        Full pipeline: detect scene boundaries → enrich frames → tag boundaries.

        Falls back gracefully if scene detection fails.
        """
        try:
            scenes = self._scene_detector.detect(video_path)
        except Exception:
            scenes = []

        enriched = self.process(frames)

        if scenes:
            scene_map = {s.timestamp_ms: s for s in scenes}
            for ef in enriched:
                for st, boundary in scene_map.items():
                    if abs(ef.timestamp_ms - st) < 2000:
                        ef.scene_boundary = boundary
                        break

        return enriched
