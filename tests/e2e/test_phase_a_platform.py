"""Phase A E2E test — Platform Primitives.

Tests all 5 new platform capabilities:
  1. Speaker Diarization + Intelligence
  2. Auto-Summary Engine
  3. Clip Extractor (FFmpeg)
  4. Custom Schema Builder + Registry
  5. Webhook Delivery (mocked HTTP)

Rules (from claude.md §0):
  - Generates synthetic data in-process (no external assets required)
  - Runs all real code; only external HTTP calls are mocked
  - Asserts correct output schema and non-empty results
  - Must pass with 0 failures before Phase A is "done"
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from temporalos.core.types import Word


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_words(sentences: List[str], gap_ms: int = 200) -> List[Word]:
    """Build a list of Word objects with realistic timestamps."""
    words: List[Word] = []
    t = 0
    for sent in sentences:
        for tok in sent.split():
            dur = len(tok) * 60 + 80  # ~140 WPM proxy
            words.append(Word(text=tok, start_ms=t, end_ms=t + dur))
            t += dur + gap_ms
        t += 1500  # 1.5s speaker-turn pause after each sentence
    return words


@pytest.fixture
def sample_words():
    return _make_words([
        "The pricing is a bit high compared to competitors",
        "Can you offer a discount for annual contracts",
        "We need to see a demo of the integration features",
        "What is your security certification and compliance posture",
        "We will definitely move forward if the price is right",
    ])


@pytest.fixture
def sample_intel():
    """Minimal VideoIntelligence-like dict for summary testing."""
    return {
        "duration_ms": 120_000,
        "overall_risk_score": 0.72,
        "segments": [
            {
                "timestamp_str": "00:00",
                "timestamp_ms": 0,
                "transcript": "The pricing is a bit high compared to competitors.",
                "extraction": {
                    "topic": "pricing",
                    "risk": "high",
                    "risk_score": 0.78,
                    "objections": ["pricing is too high", "compared to competitors"],
                    "decision_signals": [],
                    "sentiment": "negative",
                },
            },
            {
                "timestamp_str": "00:30",
                "timestamp_ms": 30_000,
                "transcript": "We will move forward if the price is right.",
                "extraction": {
                    "topic": "commitment",
                    "risk": "low",
                    "risk_score": 0.22,
                    "objections": [],
                    "decision_signals": ["move forward", "price is right"],
                    "sentiment": "positive",
                },
            },
        ],
    }


# ── 1. Speaker Diarization ────────────────────────────────────────────────────

class TestSpeakerDiarization:
    def test_mock_diarizer_assigns_labels(self, sample_words):
        from temporalos.diarization.diarizer import get_diarizer
        diarizer = get_diarizer()
        labeled = diarizer.diarize(sample_words)
        assert len(labeled) == len(sample_words)
        speakers = {w.speaker for w in labeled}
        assert speakers <= {"SPEAKER_A", "SPEAKER_B"}
        assert "SPEAKER_A" in speakers

    def test_diarizer_detects_speaker_turns(self, sample_words):
        from temporalos.diarization.diarizer import MockDiarizer
        diarizer = MockDiarizer(pause_threshold_ms=1400)
        segments = diarizer.get_segments(sample_words)
        # 5 sentences × 1500ms gap → ≥2 segments
        assert len(segments) >= 2
        for seg in segments:
            assert seg.speaker in ("SPEAKER_A", "SPEAKER_B")
            assert seg.end_ms >= seg.start_ms

    def test_segment_to_dict(self, sample_words):
        from temporalos.diarization.diarizer import MockDiarizer
        seg = MockDiarizer().get_segments(sample_words)[0]
        d = seg.to_dict()
        assert all(k in d for k in ("speaker", "start_ms", "end_ms"))

    def test_speaker_intelligence_stats(self, sample_words):
        from temporalos.diarization.diarizer import MockDiarizer
        from temporalos.diarization.speaker_intel import compute_speaker_intelligence
        labeled = MockDiarizer().diarize(sample_words)
        intel = compute_speaker_intelligence(labeled)
        assert len(intel.stats) >= 1
        d = intel.to_dict()
        assert "speaker_stats" in d
        assert "talk_ratio" in d
        ratio_total = sum(intel.talk_ratio.values())
        assert abs(ratio_total - 1.0) < 0.01


# ── 2. Auto-Summary ───────────────────────────────────────────────────────────

class TestAutoSummary:
    def test_executive_summary(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        engine = get_summary_engine()
        summary = engine.generate(sample_intel, SummaryType.EXECUTIVE)
        assert summary.type == SummaryType.EXECUTIVE
        assert len(summary.content) > 10
        assert summary.word_count > 0

    def test_action_items_summary(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        engine = get_summary_engine()
        s = engine.generate(sample_intel, SummaryType.ACTION_ITEMS)
        assert s.type == SummaryType.ACTION_ITEMS

    def test_deal_brief_has_risk(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        s = get_summary_engine().generate(sample_intel, SummaryType.DEAL_BRIEF)
        assert "risk_level" in s.sections

    def test_meeting_notes_has_sections(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        s = get_summary_engine().generate(sample_intel, SummaryType.MEETING_NOTES)
        assert "topics_covered" in s.sections
        assert "key_objections" in s.sections

    def test_summary_to_dict_schema(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        s = get_summary_engine().generate(sample_intel, SummaryType.EXECUTIVE)
        d = s.to_dict()
        assert all(k in d for k in ("type", "content", "sections", "word_count", "model"))

    def test_all_summary_types(self, sample_intel):
        from temporalos.summarization.engine import get_summary_engine, SummaryType
        engine = get_summary_engine()
        for stype in SummaryType:
            s = engine.generate(sample_intel, stype)
            assert s.content


# ── 3. Clip Extractor ─────────────────────────────────────────────────────────

class TestClipExtractor:
    @pytest.fixture
    def tiny_video(self, tmp_path) -> str:
        """Generate a 5-second silent video using FFmpeg."""
        out = tmp_path / "test.mp4"
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=5",
             "-f", "lavfi", "-i", "anullsrc=cl=mono:r=8000",
             "-t", "5", "-c:v", "libx264", "-c:a", "aac", str(out)],
            capture_output=True,
        )
        pytest.importorskip("subprocess", reason="FFmpeg required")
        if result.returncode != 0:
            pytest.skip("FFmpeg not available or encoding failed")
        return str(out)

    def test_infer_significant_clips(self, sample_intel):
        from temporalos.clips.extractor import get_clip_extractor
        extractor = get_clip_extractor()
        specs = extractor.infer_significant_clips(sample_intel["segments"], n=2)
        assert len(specs) <= 2
        for spec in specs:
            assert spec.start_ms < spec.end_ms
            assert spec.label

    def test_clip_spec_to_dict(self):
        from temporalos.clips.extractor import ClipSpec
        spec = ClipSpec(label="pricing_high", start_ms=1000, end_ms=16000, risk_score=0.8, topic="pricing")
        d = spec.to_dict("abc123")
        assert d["label"] == "pricing_high"
        assert d["start_ms"] == 1000

    def test_extract_clip_from_video(self, tiny_video, tmp_path):
        from temporalos.clips.extractor import ClipExtractor, ClipSpec
        extractor = ClipExtractor(clips_dir=tmp_path / "clips")
        spec = ClipSpec(label="test_clip", start_ms=500, end_ms=3000, risk_score=0.9)
        clip = extractor.extract(tiny_video, "test_job_123", spec)
        assert clip.path.exists()
        assert clip.size_bytes > 0
        assert clip.clip_id

    def test_list_clips_empty(self, tmp_path):
        from temporalos.clips.extractor import ClipExtractor
        extractor = ClipExtractor(clips_dir=tmp_path / "clips")
        clips = extractor.list_clips("nonexistent_job")
        assert clips == []


# ── 4. Custom Schema Builder ──────────────────────────────────────────────────

class TestSchemaRegistry:
    def test_create_and_get_schema(self, tmp_path):
        from temporalos.schemas.registry import (
            FieldDefinition, FieldType, SchemaDefinition, SchemaRegistry
        )
        registry = SchemaRegistry(schemas_dir=tmp_path / "schemas")
        schema = SchemaDefinition(
            name="Test Schema",
            vertical="sales",
            fields=[
                FieldDefinition(name="pain_point", type=FieldType.STRING, description="Key pain"),
                FieldDefinition(name="budget", type=FieldType.CATEGORY, options=["low", "medium", "high"]),
            ],
        )
        created = registry.create(schema)
        assert created.id
        retrieved = registry.get(created.id)
        assert retrieved is not None
        assert retrieved.name == "Test Schema"
        assert len(retrieved.fields) == 2

    def test_list_schemas(self, tmp_path):
        from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition, SchemaRegistry
        registry = SchemaRegistry(schemas_dir=tmp_path / "schemas")
        for i in range(3):
            registry.create(SchemaDefinition(name=f"Schema {i}", fields=[]))
        schemas = registry.list_schemas()
        assert len(schemas) == 3

    def test_delete_schema(self, tmp_path):
        from temporalos.schemas.registry import SchemaDefinition, SchemaRegistry
        registry = SchemaRegistry(schemas_dir=tmp_path / "schemas")
        s = registry.create(SchemaDefinition(name="To Delete", fields=[]))
        assert registry.get(s.id) is not None
        registry.delete(s.id)
        assert registry.get(s.id) is None

    def test_schema_to_dict(self, tmp_path):
        from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition, SchemaRegistry
        registry = SchemaRegistry(schemas_dir=tmp_path / "schemas")
        schema = registry.create(SchemaDefinition(name="Dict Test", fields=[
            FieldDefinition(name="topic", type=FieldType.STRING),
        ]))
        d = schema.to_dict()
        assert "id" in d and "name" in d and "fields" in d

    def test_build_prompt_from_schema(self, tmp_path):
        from temporalos.schemas.builder import build_prompt_from_schema
        from temporalos.schemas.registry import FieldDefinition, FieldType, SchemaDefinition
        schema = SchemaDefinition(name="Custom", fields=[
            FieldDefinition(name="budget_level", type=FieldType.CATEGORY, options=["low", "medium", "high"]),
            FieldDefinition(name="decision_maker", type=FieldType.BOOLEAN),
        ])
        prompt = build_prompt_from_schema(schema, "We have a tight budget", "No slide text")
        assert "budget_level" in prompt
        assert "decision_maker" in prompt


# ── 5. Webhook Delivery ───────────────────────────────────────────────────────

class TestWebhookDelivery:
    def test_webhook_registry_crud(self, tmp_path):
        from temporalos.webhooks.models import WebhookConfig, WebhookEvent, WebhookRegistry
        registry = WebhookRegistry(webhooks_dir=tmp_path / "webhooks")
        wh = registry.create(WebhookConfig(
            url="https://example.com/hook",
            events=[WebhookEvent.JOB_COMPLETED],
            secret="my-secret",
        ))
        assert wh.id
        assert registry.get(wh.id) is not None
        registry.delete(wh.id)
        assert registry.get(wh.id) is None

    def test_webhook_deliver_with_mock(self, tmp_path):
        from temporalos.webhooks.models import WebhookConfig, WebhookEvent, WebhookRegistry
        from temporalos.webhooks.deliverer import WebhookDeliverer
        registry = WebhookRegistry(webhooks_dir=tmp_path / "webhooks")
        registry.create(WebhookConfig(
            url="https://httpbin.org/post",
            events=[WebhookEvent.JOB_COMPLETED],
            secret="test-secret",
        ))

        with patch("temporalos.webhooks.deliverer.urllib.request.urlopen") as mock_open:
            resp = MagicMock()
            resp.status = 200
            context = MagicMock()
            context.__enter__ = lambda s: resp
            context.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = context

            deliverer = WebhookDeliverer(registry=registry)
            results = deliverer.deliver(WebhookEvent.JOB_COMPLETED, {"job_id": "test-123"})

        assert len(results) == 1
        assert results[0]["webhook_id"]
        assert results[0]["http_status"] == 200

    def test_hmac_signature_present(self, tmp_path):
        from temporalos.webhooks.models import WebhookConfig, WebhookEvent, WebhookRegistry
        from temporalos.webhooks.deliverer import WebhookDeliverer
        registry = WebhookRegistry(webhooks_dir=tmp_path / "webhooks")
        registry.create(WebhookConfig(
            url="https://httpbin.org/post",
            events=[WebhookEvent.RISK_HIGH],
            secret="s3cr3t",
        ))
        captured_headers = {}

        def fake_urlopen(req):
            captured_headers.update(dict(req.headers))
            resp = MagicMock()
            resp.status = 200
            context = MagicMock()
            context.__enter__ = lambda s: resp
            context.__exit__ = MagicMock(return_value=False)
            return context

        with patch("temporalos.webhooks.deliverer.urllib.request.urlopen", side_effect=fake_urlopen):
            deliverer = WebhookDeliverer(registry=registry)
            deliverer.deliver(WebhookEvent.RISK_HIGH, {"risk_score": 0.9})

        sig_key = next((k for k in captured_headers if "signature" in k.lower()), None)
        assert sig_key is not None, "HMAC signature header not sent"
