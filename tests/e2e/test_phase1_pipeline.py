"""
Phase 1 end-to-end test — Walking Skeleton.

Tests the complete pipeline:
  video file → frame extraction → transcription → alignment → extraction → JSON output

Rules (from claude.md §0):
  - Generates a synthetic test video using FFmpeg (no external assets)
  - Runs all real code: FFmpeg, alignment, types, API route
  - External API calls (OpenAI) are mocked
  - Asserts correct output schema and non-empty results
  - Must pass with 0 failures before Phase 1 is considered "done"
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from temporalos.alignment.aligner import align
from temporalos.core.types import AlignedSegment, ExtractionResult
from temporalos.extraction.models.gpt4o import GPT4oExtractionModel
from temporalos.ingestion.extractor import extract_frames, get_video_duration_ms


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_openai_response(payload: dict) -> MagicMock:
    choice = MagicMock()
    choice.message.content = json.dumps(payload)
    resp = MagicMock()
    resp.choices = [choice]
    return resp


_MOCK_EXTRACTION = {
    "topic": "pricing",
    "sentiment": "hesitant",
    "risk": "high",
    "risk_score": 0.75,
    "objections": ["The price seems high compared to competitors"],
    "decision_signals": ["Can you send a proposal?"],
    "confidence": 0.88,
}


# ── Phase 1 Pipeline E2E ───────────────────────────────────────────────────────


class TestPhase1Pipeline:
    """Full pipeline integration tests — no DB, no live API."""

    def test_frame_extraction_from_real_video(self, test_video_path, tmp_path):
        """FFmpeg extracts frames from a real generated video."""
        frames = extract_frames(
            video_path=test_video_path,
            output_dir=str(tmp_path / "frames"),
            interval_seconds=2,
            max_resolution=320,
        )
        assert len(frames) >= 5, "Expected at least 5 frames from a 12-second video"
        assert all(Path(f.path).exists() for f in frames), "All frame files must exist on disk"
        assert all(f.timestamp_ms >= 0 for f in frames), "All timestamps must be non-negative"
        print(f"  ✓ Extracted {len(frames)} frames")

    def test_duration_detection(self, test_video_path):
        """ffprobe correctly reads video duration."""
        ms = get_video_duration_ms(test_video_path)
        assert 10_000 <= ms <= 14_000, f"Unexpected duration: {ms} ms"
        print(f"  ✓ Duration: {ms} ms")

    def test_temporal_alignment(self, sample_frames, sample_words):
        """Alignment produces one segment per frame, with words correctly bucketed."""
        segments = align(sample_frames, sample_words)
        assert len(segments) == len(sample_frames)

        total_words_assigned = sum(len(s.words) for s in segments)
        assert total_words_assigned == len(sample_words), (
            "Every word must be assigned to exactly one segment"
        )

        # Key words in our test transcript should appear in some segment
        all_text = " ".join(s.transcript for s in segments)
        for keyword in ("pricing", "expensive", "proposal"):
            assert keyword in all_text, f"Keyword '{keyword}' missing from aligned transcript"

        print(f"  ✓ {len(segments)} segments, {total_words_assigned} words aligned")

    def test_extraction_with_mocked_openai(self, sample_segments):
        """Extraction adapter produces valid ExtractionResult from a mocked API response."""
        model = GPT4oExtractionModel(model="gpt-4o", api_key="sk-test")
        # Use first segment with actual words
        seg = next(s for s in sample_segments if s.words)

        with patch.object(
            model._client.chat.completions,
            "create",
            return_value=_mock_openai_response(_MOCK_EXTRACTION),
        ):
            result = model.extract(seg)

        assert isinstance(result, ExtractionResult)
        assert result.topic == "pricing"
        assert result.risk == "high"
        assert 0.0 <= result.risk_score <= 1.0
        assert isinstance(result.objections, list)
        assert isinstance(result.decision_signals, list)
        assert result.model_name == "gpt4o"
        print(f"  ✓ Extracted: topic={result.topic} risk={result.risk} score={result.risk_score}")

    def test_full_pipeline_output_schema(self, sample_frames, sample_words):
        """
        End-to-end pipeline: frames + words → align → extract → structured JSON.
        Validates the final output shape that the API will return.
        """
        segments = align(sample_frames, sample_words)
        model = GPT4oExtractionModel(model="gpt-4o", api_key="sk-test")

        results: list[dict] = []
        with patch.object(
            model._client.chat.completions,
            "create",
            return_value=_mock_openai_response(_MOCK_EXTRACTION),
        ):
            for seg in segments:
                if len(seg.words) < 3:
                    continue
                ext = model.extract(seg)
                results.append({"timestamp": seg.timestamp_str, **ext.to_dict()})

        assert len(results) > 0, "Pipeline must produce at least one extraction result"

        overall_risk = round(sum(r["risk_score"] for r in results) / len(results), 2)
        output = {"segments": results, "overall_risk_score": overall_risk}

        # ── Schema assertions ──────────────────────────────────────────────────
        assert "segments" in output
        assert "overall_risk_score" in output
        assert 0.0 <= output["overall_risk_score"] <= 1.0

        for seg in output["segments"]:
            assert "timestamp" in seg, "Each segment must have a timestamp"
            assert "topic" in seg
            assert "customer_sentiment" in seg
            assert "risk" in seg
            assert "risk_score" in seg
            assert isinstance(seg["objections"], list)
            assert isinstance(seg["decision_signals"], list)
            assert seg["risk"] in {"low", "medium", "high"}
            assert seg["customer_sentiment"] in {"positive", "neutral", "negative", "hesitant"}

        print(
            f"  ✓ Output: {len(results)} segments, "
            f"overall_risk={output['overall_risk_score']}"
        )
        print(f"  ✓ Schema validation passed for all {len(results)} segments")


# ── FastAPI route E2E ──────────────────────────────────────────────────────────


class TestPhase1API:
    """End-to-end test of the FastAPI /process route."""

    @pytest.fixture(autouse=True)
    def client(self):
        """
        Create a TestClient with DB init skipped (no real Postgres in CI).
        We patch init_db and the background pipeline runner.
        """
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app
            self._client = TestClient(app, raise_server_exceptions=True)

    def test_health_endpoint(self):
        resp = self._client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "temporalos"

    def test_process_and_poll_lifecycle(self, test_video_path):
        """
        Submit a real video, verify 202 + job_id returned, then poll.
        The background pipeline runner is patched so the test doesn't need
        OpenAI keys or the Whisper model to be downloaded.
        """
        from temporalos.api.routes import process as process_module

        def _fake_pipeline(job_id: str, video_path: str, frames_dir: str) -> None:
            process_module._jobs[job_id]["status"] = "completed"
            process_module._jobs[job_id]["result"] = {
                "segments": [
                    {
                        "timestamp": "00:02",
                        "topic": "pricing",
                        "customer_sentiment": "hesitant",
                        "risk": "high",
                        "risk_score": 0.75,
                        "objections": ["Too expensive"],
                        "decision_signals": [],
                        "model": "gpt4o",
                    }
                ],
                "overall_risk_score": 0.75,
                "segment_count": 1,
            }

        with (
            open(test_video_path, "rb") as f,
            patch.object(process_module, "_run_pipeline", side_effect=_fake_pipeline),
        ):
            resp = self._client.post(
                "/api/v1/process",
                files={"file": ("test_call.mp4", f, "video/mp4")},
            )

        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "job_id" in data
        job_id = data["job_id"]

        # Poll
        poll = self._client.get(f"/api/v1/jobs/{job_id}")
        assert poll.status_code == 200
        job = poll.json()
        assert job["status"] == "completed"
        assert "result" in job
        result = job["result"]
        assert "segments" in result
        assert "overall_risk_score" in result
        assert len(result["segments"]) == 1
        assert result["segments"][0]["topic"] == "pricing"
        print(f"  ✓ Job {job_id}: status=completed, {len(result['segments'])} segment(s)")

    def test_process_unsupported_format_rejected(self):
        resp = self._client.post(
            "/api/v1/process",
            files={"file": ("audio.txt", b"not a video", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported format" in resp.json()["detail"]

    def test_poll_unknown_job_returns_404(self):
        resp = self._client.get("/api/v1/jobs/nonexistent-job-id")
        assert resp.status_code == 404
