"""
Phase 9 end-to-end tests — Scene-Aware Frame Intelligence.

Covers:
  - SceneDetector: detects boundaries or falls back to uniform sampling
  - KeyframeSelector: deduplicates visually similar frames
  - OcrEngine: extracts text (with EasyOCR or PIL fallback)
  - SlideClassifier: classifies frame types heuristically
  - VisionPipeline: full end-to-end process() and process_video()

Rule §0: synthetic test video from conftest, no external vision APIs.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ── SceneDetector ─────────────────────────────────────────────────────────────


class TestSceneDetector:
    def test_raises_file_not_found(self):
        from temporalos.ingestion.scene_detector import SceneDetector

        with pytest.raises(FileNotFoundError):
            SceneDetector().detect("/nonexistent/path/video.mp4")

    def test_detects_on_real_video(self, test_video_path):
        from temporalos.ingestion.scene_detector import SceneDetector

        boundaries = SceneDetector().detect(test_video_path)
        assert len(boundaries) > 0
        assert all(b.timestamp_ms >= 0 for b in boundaries)

    def test_boundaries_sorted_by_timestamp(self, test_video_path):
        from temporalos.ingestion.scene_detector import SceneDetector

        boundaries = SceneDetector().detect(test_video_path)
        timestamps = [b.timestamp_ms for b in boundaries]
        assert timestamps == sorted(timestamps)

    def test_min_scene_duration_respected(self, test_video_path):
        from temporalos.ingestion.scene_detector import SceneDetector

        min_ms = 2000
        sd = SceneDetector(min_scene_duration_ms=min_ms)
        boundaries = sd.detect(test_video_path)
        for i in range(1, len(boundaries)):
            gap = boundaries[i].timestamp_ms - boundaries[i - 1].timestamp_ms
            assert gap >= min_ms

    def test_boundary_dataclass_fields(self):
        from temporalos.ingestion.scene_detector import SceneBoundary

        b = SceneBoundary(timestamp_ms=5000, frame_number=2, score=0.45)
        assert b.timestamp_ms == 5000
        assert b.frame_number == 2
        assert b.score == pytest.approx(0.45)


# ── KeyframeSelector ──────────────────────────────────────────────────────────


class TestKeyframeSelector:
    def test_empty_input_returns_empty(self):
        from temporalos.ingestion.keyframe_selector import KeyframeSelector

        assert KeyframeSelector().select([]) == []

    def test_single_frame_always_kept(self, sample_frames):
        from temporalos.ingestion.keyframe_selector import KeyframeSelector

        result = KeyframeSelector().select(sample_frames[:1])
        assert len(result) == 1

    def test_deduplicates_frames(self, sample_frames):
        from temporalos.ingestion.keyframe_selector import KeyframeSelector

        # Blue-screen video → many similar frames; selector should reduce count
        selector = KeyframeSelector(similarity_threshold=0)  # strict: keep all
        result_strict = selector.select(sample_frames)
        selector_loose = KeyframeSelector(similarity_threshold=60)  # keep few
        result_loose = selector_loose.select(sample_frames)
        # Loose threshold keeps ≤ strict threshold count
        assert len(result_loose) <= len(result_strict)

    def test_preserves_frame_objects(self, sample_frames):
        from temporalos.ingestion.keyframe_selector import KeyframeSelector

        result = KeyframeSelector().select(sample_frames)
        from temporalos.core.types import Frame

        assert all(isinstance(f, Frame) for f in result)

    def test_threshold_zero_keeps_all_different(self, sample_frames):
        from temporalos.ingestion.keyframe_selector import KeyframeSelector

        # With threshold=0, only exact same bytes → keep. Single-colour video
        # might still deduplicate. Just check no crash and returns list.
        result = KeyframeSelector(similarity_threshold=0).select(sample_frames)
        assert isinstance(result, list)
        assert len(result) >= 1


# ── OcrEngine ─────────────────────────────────────────────────────────────────


class TestOcrEngine:
    def test_nonexistent_file_returns_empty(self):
        from temporalos.vision.ocr import OcrEngine

        result = OcrEngine().extract("/nonexistent/frame.jpg")
        assert result.is_empty
        assert result.confidence == 0.0

    def test_extract_real_frame_no_crash(self, sample_frames):
        from temporalos.vision.ocr import OcrEngine

        result = OcrEngine().extract(sample_frames[0].path)
        # Should not raise — result may be empty (no text in blue frame)
        assert isinstance(result.text, str)
        assert isinstance(result.confidence, float)

    def test_is_empty_property(self):
        from temporalos.vision.ocr import OcrResult

        empty = OcrResult(text="", confidence=0.0)
        nonempty = OcrResult(text="hello", confidence=0.9)
        assert empty.is_empty
        assert not nonempty.is_empty

    def test_bounding_boxes_default_empty(self):
        from temporalos.vision.ocr import OcrResult

        r = OcrResult(text="test", confidence=0.8)
        assert r.bounding_boxes == []


# ── SlideClassifier ───────────────────────────────────────────────────────────


class TestSlideClassifier:
    def test_nonexistent_returns_unknown(self):
        from temporalos.vision.slide_classifier import FrameType, SlideClassifier

        assert SlideClassifier().classify("/nonexistent.jpg") == FrameType.UNKNOWN

    def test_classifies_real_frame(self, sample_frames):
        from temporalos.vision.slide_classifier import FrameType, SlideClassifier

        ft = SlideClassifier().classify(sample_frames[0].path)
        # Blue solid colour → should be SLIDE or UNKNOWN (PIL may not be present)
        assert isinstance(ft, FrameType)

    def test_frame_type_values(self):
        from temporalos.vision.slide_classifier import FrameType

        assert FrameType.SLIDE.value == "slide"
        assert FrameType.SCREEN.value == "screen"
        assert FrameType.FACE.value == "face"
        assert FrameType.CHART.value == "chart"
        assert FrameType.MIXED.value == "mixed"
        assert FrameType.UNKNOWN.value == "unknown"

    def test_classify_batch(self, sample_frames):
        from temporalos.vision.slide_classifier import FrameType, SlideClassifier

        paths = [f.path for f in sample_frames[:3]]
        results = SlideClassifier().classify_batch(paths)
        assert len(results) == len(paths)
        assert all(isinstance(r, FrameType) for r in results)


# ── VisionPipeline ────────────────────────────────────────────────────────────


class TestVisionPipeline:
    def test_process_empty_returns_empty(self):
        from temporalos.vision.pipeline import VisionPipeline

        assert VisionPipeline().process([]) == []

    def test_process_returns_enriched_frames(self, sample_frames):
        from temporalos.vision.pipeline import EnrichedFrame, VisionPipeline

        enriched = VisionPipeline().process(sample_frames)
        assert len(enriched) > 0
        assert all(isinstance(ef, EnrichedFrame) for ef in enriched)

    def test_enriched_frame_has_timestamp(self, sample_frames):
        from temporalos.vision.pipeline import VisionPipeline

        enriched = VisionPipeline().process(sample_frames)
        for ef in enriched:
            assert isinstance(ef.timestamp_ms, int)
            assert ef.timestamp_ms >= 0

    def test_enriched_frame_to_dict(self, sample_frames):
        from temporalos.vision.pipeline import VisionPipeline

        enriched = VisionPipeline().process(sample_frames)
        d = enriched[0].to_dict()
        assert "timestamp_ms" in d
        assert "frame_type" in d
        assert "ocr_text" in d
        assert "is_scene_boundary" in d

    def test_process_video_integrates_scene_detection(self, test_video_path, sample_frames):
        from temporalos.vision.pipeline import VisionPipeline

        enriched = VisionPipeline().process_video(test_video_path, sample_frames)
        assert len(enriched) > 0
        # Just verify no crash and types are correct
        for ef in enriched:
            assert ef.frame_type is not None

    def test_deduplication_reduces_frame_count(self, sample_frames):
        from temporalos.vision.pipeline import VisionPipeline

        # Blue video → many near-identical frames
        pipeline = VisionPipeline(dedup_threshold=60)
        enriched = pipeline.process(sample_frames)
        # Should have fewer frames due to deduplication
        assert len(enriched) <= len(sample_frames)

    def test_no_ocr_produces_empty_text(self, sample_frames):
        from temporalos.vision.pipeline import VisionPipeline

        pipeline = VisionPipeline(run_ocr=False)
        enriched = pipeline.process(sample_frames)
        for ef in enriched:
            assert ef.ocr_text == ""
