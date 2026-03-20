"""
Local SLM Pipeline — Phase 5.

Full end-to-end video → structured intelligence with zero external API calls.
Chains:
  1. FFmpeg frame extraction  (already in Phase 1)
  2. faster-whisper ASR        (already in Phase 1)
  3. Temporal alignment        (already in Phase 1)
  4. Qwen2.5-VL vision         (added in Phase 2, optional)
  5. Fine-tuned extraction     (added in Phase 4) — falls back to rule-based stub

Benchmark target (Phase 5):
  - Accuracy within 5% F1 of GPT-4o baseline
  - < 3x wall-clock time vs API pipeline on equivalent hardware
  - $0.00 per video (no API costs)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..core.types import AlignedSegment, ExtractionResult, Frame, VideoIntelligence
from ..observability.telemetry import get_tracer


@dataclass
class LocalPipelineResult:
    """Complete output of a local pipeline run."""

    video_path: str
    video_intelligence: VideoIntelligence
    stage_latencies_ms: dict[str, int] = field(default_factory=dict)
    whisper_model: str = ""
    extraction_model: str = ""
    total_latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "intelligence": self.video_intelligence.to_dict()
            if hasattr(self.video_intelligence, "to_dict")
            else {},
            "stage_latencies_ms": self.stage_latencies_ms,
            "whisper_model": self.whisper_model,
            "extraction_model": self.extraction_model,
            "total_latency_ms": self.total_latency_ms,
        }


class LocalPipeline:
    """
    Phase 5 — Local SLM Pipeline.

    Runs entirely on local hardware with no external API calls.
    All models are loaded lazily on first use and cached for subsequent calls.
    """

    def __init__(
        self,
        whisper_model: str = "base",
        vision_model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct",
        adapter_path: str = "",
        frame_interval_seconds: int = 2,
        max_resolution: int = 1024,
    ) -> None:
        self._whisper_model = whisper_model
        self._vision_model_id = vision_model_id
        self._adapter_path = adapter_path
        self._frame_interval = frame_interval_seconds
        self._max_resolution = max_resolution
        self._extractor_cache: object | None = None

    @classmethod
    def from_settings(cls) -> "LocalPipeline":
        from ..config import get_settings
        s = get_settings()
        return cls(
            whisper_model=s.audio.whisper_model,
            vision_model_id="Qwen/Qwen2.5-VL-7B-Instruct",
            adapter_path=s.finetuning.adapter_path,
            frame_interval_seconds=s.video.frame_interval_seconds,
            max_resolution=s.video.max_resolution,
        )

    def process(
        self,
        video_path: str,
        output_dir: str | None = None,
        use_vision: bool = False,
    ) -> LocalPipelineResult:
        """
        Run the full local pipeline on a video file.

        Parameters
        ----------
        video_path   : path to the video file
        output_dir   : where to write extracted frames (temp dir if None)
        use_vision   : enable Qwen2.5-VL vision analysis (requires ~12 GB RAM)
        """
        tracer = get_tracer()
        total_start = time.time()
        latencies: dict[str, int] = {}

        with tracer.start_as_current_span("local_pipeline.process") as span:
            span.set_attribute("pipeline.video_path", video_path)
            span.set_attribute("pipeline.whisper_model", self._whisper_model)
            span.set_attribute("pipeline.use_vision", use_vision)

            t0 = time.time()
            frames = self._extract_frames(video_path, output_dir)
            latencies["frame_extraction_ms"] = int((time.time() - t0) * 1000)

            t0 = time.time()
            words = self._transcribe(video_path)
            latencies["transcription_ms"] = int((time.time() - t0) * 1000)

            t0 = time.time()
            segments = self._align(frames, words)
            latencies["alignment_ms"] = int((time.time() - t0) * 1000)

            if use_vision:
                t0 = time.time()
                self._add_vision_context(segments)
                latencies["vision_ms"] = int((time.time() - t0) * 1000)

            t0 = time.time()
            extractor = self._get_extractor()
            extractions = extractor.extract_batch(
                [s for s in segments if s.words]
            )
            latencies["extraction_ms"] = int((time.time() - t0) * 1000)

            total_ms = int((time.time() - total_start) * 1000)
            span.set_attribute("pipeline.total_latency_ms", total_ms)

            # Pair extractions back with their segments for VideoIntelligence
            non_empty = [s for s in segments if s.words]
            paired = list(zip(non_empty, extractions))

            return LocalPipelineResult(
                video_path=video_path,
                video_intelligence=VideoIntelligence(
                    video_path=video_path,
                    duration_ms=total_ms,
                    segments=paired,
                ),
                stage_latencies_ms=latencies,
                whisper_model=self._whisper_model,
                extraction_model=extractor.name,
                total_latency_ms=total_ms,
            )

    def _extract_frames(self, video_path: str, output_dir: str | None) -> list[Frame]:
        import tempfile
        from ..ingestion.extractor import extract_frames
        frames_dir = output_dir or tempfile.mkdtemp(prefix="temporalos_local_")
        return extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            interval_seconds=self._frame_interval,
            max_resolution=self._max_resolution,
        )

    def _transcribe(self, video_path: str) -> list:
        from ..audio.whisper import transcribe
        from ..config import get_settings
        settings = get_settings()
        language = settings.audio.language if settings.audio.language != "auto" else None
        return transcribe(
            video_path=video_path,
            model_name=self._whisper_model,
            language=language,
        )

    def _align(self, frames: list, words: list) -> list[AlignedSegment]:
        from ..alignment.aligner import align
        return align(frames, words)

    def _add_vision_context(self, segments: list[AlignedSegment]) -> None:
        try:
            from ..vision.models.qwen_vl import QwenVLModel
            vision = QwenVLModel(model_id=self._vision_model_id)
            for seg in segments:
                if seg.frame and seg.frame.path:
                    try:
                        analysis = vision.analyze(seg.frame)
                        seg.frame.__dict__["vision_description"] = analysis.description
                    except Exception:
                        pass
        except (ImportError, Exception):
            pass

    def _get_extractor(self) -> object:
        if self._extractor_cache is not None:
            return self._extractor_cache
        from ..extraction.models.finetuned import FineTunedExtractionModel
        model = FineTunedExtractionModel(adapter_path=self._adapter_path)
        if model.is_available:
            self._extractor_cache = model
        else:
            self._extractor_cache = _RuleBasedExtractor()
        return self._extractor_cache


class _RuleBasedExtractor:
    """
    Zero-dependency fallback extractor.
    Uses keyword matching — not production-accurate, but keeps the pipeline
    running when no fine-tuned model is available.
    """

    name = "rule_based"

    _HIGH_RISK_WORDS = {
        "expensive", "cost", "price", "budget", "competitor",
        "cancel", "switch", "alternative", "too much",
    }
    _OBJECTION_PATTERNS = [
        "too expensive", "too costly", "can't afford", "budget is tight",
        "already using", "hard to justify", "not sure if",
    ]
    _DECISION_PATTERNS = [
        "send a proposal", "schedule a demo", "bring in my manager",
        "need to think", "let me discuss", "move forward", "next steps",
    ]
    _TOPIC_KEYWORDS = {
        "pricing": ["price", "cost", "pricing", "expensive", "budget", "plan"],
        "features": ["feature", "capability", "can it", "does it", "integration"],
        "competition": ["competitor", "versus", "compared to", "alternative"],
        "timeline": ["when", "timeline", "deadline", "date", "launch"],
        "security": ["security", "compliance", "gdpr", "soc2", "encryption"],
        "support": ["support", "help", "service", "onboarding"],
    }

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        transcript = " ".join(w.text for w in segment.words).lower()
        topic = self._detect_topic(transcript)
        risk_words = sum(1 for w in self._HIGH_RISK_WORDS if w in transcript)
        risk_score = min(1.0, risk_words / 5.0)
        risk = "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low"
        objections = [p for p in self._OBJECTION_PATTERNS if p in transcript]
        signals = [p for p in self._DECISION_PATTERNS if p in transcript]
        return ExtractionResult(
            topic=topic,
            sentiment="hesitant" if risk == "high" else "neutral",
            risk=risk,
            risk_score=risk_score,
            objections=objections,
            decision_signals=signals,
            confidence=0.4,
            model_name=self.name,
            latency_ms=0,
        )

    def extract_batch(self, segments: list) -> list[ExtractionResult]:
        return [self.extract(s) for s in segments]

    def _detect_topic(self, transcript: str) -> str:
        for topic, keywords in self._TOPIC_KEYWORDS.items():
            if any(kw in transcript for kw in keywords):
                return topic
        return "other"
