"""OCR extraction from video frames.

Primary backend: EasyOCR (lazy-imported, requires `pip install easyocr`)
Fallback: PIL image analysis (returns stub text with image dimensions)
Final fallback: empty result (safe for CI without any vision deps)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OcrResult:
    """Text and bounding-box data extracted from a single frame."""

    text: str
    confidence: float
    bounding_boxes: list[dict] = field(default_factory=list)
    # Each box: {"text": str, "confidence": float, "bbox": [x1, y1, x2, y2, x3, y3, x4, y4]}

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class OcrEngine:
    """
    OCR engine with EasyOCR as primary backend and graceful fallbacks.

    Safe in CI environments without GPU or heavy vision dependencies.
    """

    def __init__(self, languages: list[str] | None = None, use_gpu: bool = False) -> None:
        self._languages = languages or ["en"]
        self._use_gpu = use_gpu
        self._reader = None  # lazy init

    def _get_reader(self):
        if self._reader is not None:
            return self._reader
        try:
            import easyocr  # type: ignore[import]

            self._reader = easyocr.Reader(self._languages, gpu=self._use_gpu, verbose=False)
        except (ImportError, Exception):
            self._reader = None
        return self._reader

    def extract(self, image_path: str) -> OcrResult:
        """Extract text from an image file."""
        if not Path(image_path).exists():
            return OcrResult(text="", confidence=0.0)

        reader = self._get_reader()
        if reader is not None:
            return self._easyocr_extract(reader, image_path)
        return self._pil_fallback(image_path)

    def _easyocr_extract(self, reader, image_path: str) -> OcrResult:
        try:
            results = reader.readtext(image_path)
            if not results:
                return OcrResult(text="", confidence=0.0)
            boxes, texts, confs = [], [], []
            for bbox, text, conf in results:
                flat_bbox = [int(v) for point in bbox for v in point]
                boxes.append({"text": text, "confidence": float(conf), "bbox": flat_bbox})
                texts.append(text)
                confs.append(float(conf))
            return OcrResult(
                text=" ".join(texts),
                confidence=sum(confs) / len(confs),
                bounding_boxes=boxes,
            )
        except Exception:
            return self._pil_fallback(image_path)

    @staticmethod
    def _pil_fallback(image_path: str) -> OcrResult:
        try:
            from PIL import Image  # type: ignore[import]

            img = Image.open(image_path)
            w, h = img.size
            return OcrResult(text=f"[frame {w}x{h}]", confidence=0.1)
        except (ImportError, Exception):
            return OcrResult(text="", confidence=0.0)
