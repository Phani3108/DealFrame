"""
Phase 5 end-to-end test — Local SLM Pipeline.

Tests the fully local pipeline:
  video → frames → transcription → alignment → (rule-based) extraction → result

Rules (from claude.md §0):
  - Uses a real synthetic test video (from conftest.py)
  - Whisper transcription is mocked to avoid GPU requirement
  - Rule-based extractor is tested directly (no GPU needed)
  - Fine-tuned extractor fallback path is verified
  - Must pass with 0 failures before Phase 5 is "done"
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from temporalos.core.types import AlignedSegment, ExtractionResult, Frame, Word
from temporalos.local.benchmark import BenchmarkResult, BenchmarkRunner
from temporalos.local.pipeline import LocalPipeline, LocalPipelineResult, _RuleBasedExtractor


# ── _RuleBasedExtractor ───────────────────────────────────────────────────────


class TestRuleBasedExtractor:
    def _seg(self, text: str) -> AlignedSegment:
        frame = Frame(path="", timestamp_ms=0)
        words = [Word(text=w, start_ms=i * 200, end_ms=(i + 1) * 200) for i, w in enumerate(text.split())]
        return AlignedSegment(timestamp_ms=0, frame=frame, words=words)

    def test_pricing_topic_detected(self):
        ext = _RuleBasedExtractor().extract(self._seg("the price seems too expensive for our budget"))
        assert ext.topic == "pricing"

    def test_competition_topic_detected(self):
        ext = _RuleBasedExtractor().extract(self._seg("we are already using a competitor"))
        assert ext.topic == "competition"

    def test_features_topic_detected(self):
        ext = _RuleBasedExtractor().extract(self._seg("does it have the feature for integration"))
        assert ext.topic == "features"

    def test_other_topic_fallback(self):
        ext = _RuleBasedExtractor().extract(self._seg("hello world this is unrelated"))
        assert ext.topic == "other"

    def test_high_risk_detected(self):
        text = "cost is too much price competitor cancel switch alternative budget too expensive"
        ext = _RuleBasedExtractor().extract(self._seg(text))
        assert ext.risk == "high"
        assert ext.risk_score > 0.6

    def test_low_risk_plain_segment(self):
        ext = _RuleBasedExtractor().extract(self._seg("thank you for your time today"))
        assert ext.risk == "low"
        assert ext.risk_score == 0.0

    def test_objection_extracted(self):
        ext = _RuleBasedExtractor().extract(self._seg("this is just too expensive for us"))
        assert "too expensive" in ext.objections

    def test_decision_signal_extracted(self):
        ext = _RuleBasedExtractor().extract(self._seg("let me discuss with my team and move forward next steps"))
        assert any("move forward" in s or "let me discuss" in s for s in ext.decision_signals)

    def test_confidence_is_low_constant(self):
        ext = _RuleBasedExtractor().extract(self._seg("anything goes here"))
        assert ext.confidence == 0.4

    def test_model_name_is_rule_based(self):
        ext = _RuleBasedExtractor().extract(self._seg("test segment"))
        assert ext.model_name == "rule_based"

    def test_extract_batch_returns_correct_count(self):
        extractor = _RuleBasedExtractor()
        segments = [self._seg(f"segment number {i}") for i in range(5)]
        results = extractor.extract_batch(segments)
        assert len(results) == 5
        assert all(isinstance(r, ExtractionResult) for r in results)

    def test_empty_segment_returns_result(self):
        frame = Frame(path="", timestamp_ms=0)
        empty_seg = AlignedSegment(timestamp_ms=0, frame=frame, words=[])
        ext = _RuleBasedExtractor().extract(empty_seg)
        assert isinstance(ext, ExtractionResult)
        assert ext.risk == "low"


# ── LocalPipeline ─────────────────────────────────────────────────────────────


class TestLocalPipeline:
    def test_from_settings_constructs(self):
        pipeline = LocalPipeline.from_settings()
        assert isinstance(pipeline, LocalPipeline)

    def test_process_with_real_video_and_mocked_whisper(self, test_video_path, tmp_path):
        """Full pipeline on real video — whisper mocked to avoid GPU."""
        mock_word = Word(text="pricing", start_ms=1000, end_ms=1500)

        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline = LocalPipeline(
                whisper_model="base",
                adapter_path="",
                frame_interval_seconds=3,
                max_resolution=320,
            )
            result = pipeline.process(str(test_video_path), output_dir=str(tmp_path / "frames"))

        assert isinstance(result, LocalPipelineResult)
        assert result.video_path == str(test_video_path)
        assert result.total_latency_ms > 0
        assert result.extraction_model in ("rule_based", "finetuned")
        assert isinstance(result.stage_latencies_ms, dict)
        assert "frame_extraction_ms" in result.stage_latencies_ms

    def test_process_stage_latencies_all_present(self, test_video_path, tmp_path):
        mock_word = Word(text="test", start_ms=500, end_ms=1000)
        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline = LocalPipeline(whisper_model="base", adapter_path="", frame_interval_seconds=4)
            result = pipeline.process(str(test_video_path), output_dir=str(tmp_path / "frames"))

        assert "frame_extraction_ms" in result.stage_latencies_ms
        assert "transcription_ms" in result.stage_latencies_ms
        assert "alignment_ms" in result.stage_latencies_ms
        assert "extraction_ms" in result.stage_latencies_ms

    def test_process_uses_rule_based_fallback_when_no_adapter(self, test_video_path, tmp_path):
        mock_word = Word(text="price", start_ms=0, end_ms=500)
        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline = LocalPipeline(whisper_model="base", adapter_path="")
            result = pipeline.process(str(test_video_path), output_dir=str(tmp_path / "frames"))

        assert result.extraction_model == "rule_based"

    def test_video_intelligence_has_segments(self, test_video_path, tmp_path):
        mock_word = Word(text="the price is too expensive", start_ms=1000, end_ms=1500)
        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline = LocalPipeline(whisper_model="base", adapter_path="", frame_interval_seconds=3)
            result = pipeline.process(str(test_video_path), output_dir=str(tmp_path / "frames"))

        assert hasattr(result.video_intelligence, "segments")

    def test_to_dict_shape(self, test_video_path, tmp_path):
        mock_word = Word(text="features", start_ms=2000, end_ms=2500)
        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline = LocalPipeline(whisper_model="base", adapter_path="", frame_interval_seconds=4)
            result = pipeline.process(str(test_video_path), output_dir=str(tmp_path / "frames"))

        d = result.to_dict()
        assert "video_path" in d
        assert "stage_latencies_ms" in d
        assert "whisper_model" in d
        assert "extraction_model" in d
        assert "total_latency_ms" in d

    def test_extractor_cached_across_calls(self, test_video_path, tmp_path):
        """_get_extractor() should return the same object on second call."""
        mock_word = Word(text="test", start_ms=0, end_ms=200)
        pipeline = LocalPipeline(whisper_model="base", adapter_path="")
        with patch("temporalos.local.pipeline.LocalPipeline._transcribe", return_value=[mock_word]):
            pipeline.process(str(test_video_path), output_dir=str(tmp_path / "f1"))
        extractor1 = pipeline._get_extractor()
        extractor2 = pipeline._get_extractor()
        assert extractor1 is extractor2


# ── BenchmarkRunner ───────────────────────────────────────────────────────────


class TestBenchmarkRunner:
    def _mock_pipeline(self, total_ms: int = 5000) -> MagicMock:
        mock_word = Word(text="price", start_ms=0, end_ms=500)
        frame = Frame(path="", timestamp_ms=0)
        seg = AlignedSegment(timestamp_ms=0, frame=frame, words=[mock_word])

        from temporalos.core.types import VideoIntelligence
        ext = ExtractionResult("pricing", "hesitant", "high", 0.7, [], [], 0.8, "rule_based", 50)
        vi = VideoIntelligence(video_path="test.mp4", duration_ms=10000, segments=[(seg, ext)])

        mock_result = MagicMock()
        mock_result.video_path = "test.mp4"
        mock_result.video_intelligence = vi
        mock_result.stage_latencies_ms = {"frame_extraction_ms": 200, "extraction_ms": 300}
        mock_result.extraction_model = "rule_based"
        mock_result.total_latency_ms = total_ms

        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = mock_result
        return mock_pipeline

    def test_run_local_returns_benchmark_result(self, test_video_path):
        runner = BenchmarkRunner()
        result = runner.run_local(str(test_video_path), self._mock_pipeline(3000))
        assert isinstance(result, BenchmarkResult)
        assert result.total_latency_ms == 3000
        assert result.error == ""

    def test_run_local_captures_error(self, test_video_path):
        broken_pipeline = MagicMock()
        broken_pipeline.process.side_effect = RuntimeError("GPU OOM")
        runner = BenchmarkRunner()
        result = runner.run_local(str(test_video_path), broken_pipeline)
        assert result.error == "GPU OOM"

    def test_compare_computes_ratio(self, test_video_path):
        runner = BenchmarkRunner()
        local = runner.run_local(str(test_video_path), self._mock_pipeline(6000))
        api_result = BenchmarkResult("gpt4o", str(test_video_path), total_latency_ms=3000)
        comparison = runner.compare(local, api_result, segments_count=5)
        assert comparison.latency_ratio == pytest.approx(2.0)

    def test_compare_to_dict_shape(self, test_video_path):
        runner = BenchmarkRunner()
        local = runner.run_local(str(test_video_path), self._mock_pipeline(3000))
        api = BenchmarkResult("gpt4o", "test.mp4", total_latency_ms=2000)
        comp = runner.compare(local, api)
        d = comp.to_dict()
        assert "local" in d
        assert "api" in d
        assert "latency_ratio" in d
        assert "verdict" in d
        assert "cost_savings_usd" in d

    def test_compare_cost_savings_positive(self, test_video_path):
        runner = BenchmarkRunner()
        local = runner.run_local(str(test_video_path), self._mock_pipeline(3000))
        api = BenchmarkResult("gpt4o", "test.mp4", total_latency_ms=2000)
        comp = runner.compare(local, api, segments_count=10)
        assert comp.cost_savings_usd > 0.0  # local is always cheaper than API

    def test_local_faster_verdict(self):
        local = BenchmarkResult("rule_based", "test.mp4", total_latency_ms=1000)
        api = BenchmarkResult("gpt4o", "test.mp4", total_latency_ms=2000)
        runner = BenchmarkRunner()
        comp = runner.compare(local, api, segments_count=5)
        assert comp.local_is_faster is True
        assert comp._verdict() == "local_recommended"

    def test_local_slow_verdict(self):
        local = BenchmarkResult("rule_based", "test.mp4", total_latency_ms=10000)
        api = BenchmarkResult("gpt4o", "test.mp4", total_latency_ms=2000)
        runner = BenchmarkRunner()
        comp = runner.compare(local, api, segments_count=5)
        assert comp._verdict() == "local_too_slow"


# ── Local API tests ────────────────────────────────────────────────────────────


class TestLocalAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, test_video_path):
        self._video_path = test_video_path
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app
            self._client = TestClient(app, raise_server_exceptions=True)
            yield

    def _fake_pipeline_run(self, job_id: str, video_path: str, use_vision: bool) -> None:
        from temporalos.api.routes.local import _local_jobs
        from temporalos.core.types import VideoIntelligence

        _local_jobs[job_id].update({
            "status": "completed",
            "result": {
                "video_path": video_path,
                "intelligence": {},
                "stage_latencies_ms": {"frame_extraction_ms": 100},
                "whisper_model": "base",
                "extraction_model": "rule_based",
                "total_latency_ms": 1200,
            },
            "extraction_model": "rule_based",
            "total_latency_ms": 1200,
        })

    def test_status_endpoint_returns_model_info(self):
        resp = self._client.get("/api/v1/local/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "whisper_available" in data
        assert "finetuned_adapter_available" in data
        assert "cost_per_video_usd" in data
        assert data["cost_per_video_usd"] == 0.0

    def test_process_returns_202_with_job_id(self):
        with patch(
            "temporalos.api.routes.local._run_local",
            side_effect=self._fake_pipeline_run,
        ):
            with open(self._video_path, "rb") as f:
                resp = self._client.post(
                    "/api/v1/local/process",
                    files={"file": ("test.mp4", f, "video/mp4")},
                )
        assert resp.status_code == 202
        assert "job_id" in resp.json()

    def test_process_unsupported_format_rejected(self):
        resp = self._client.post(
            "/api/v1/local/process",
            files={"file": ("file.xyz", BytesIO(b"data"), "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_poll_job_returns_status(self):
        with patch(
            "temporalos.api.routes.local._run_local",
            side_effect=self._fake_pipeline_run,
        ):
            with open(self._video_path, "rb") as f:
                submit = self._client.post(
                    "/api/v1/local/process",
                    files={"file": ("test.mp4", f, "video/mp4")},
                )
        job_id = submit.json()["job_id"]
        poll = self._client.get(f"/api/v1/local/process/{job_id}")
        assert poll.status_code == 200
        data = poll.json()
        assert data["status"] == "completed"
        assert "result" in data

    def test_poll_unknown_job_returns_404(self):
        resp = self._client.get("/api/v1/local/process/does-not-exist")
        assert resp.status_code == 404

    def test_list_local_jobs(self):
        with patch(
            "temporalos.api.routes.local._run_local",
            side_effect=self._fake_pipeline_run,
        ):
            with open(self._video_path, "rb") as f:
                self._client.post(
                    "/api/v1/local/process",
                    files={"file": ("test.mp4", f, "video/mp4")},
                )
        resp = self._client.get("/api/v1/local/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert data["total"] >= 1
