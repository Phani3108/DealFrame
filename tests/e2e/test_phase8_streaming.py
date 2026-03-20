"""
Phase 8 end-to-end tests — Real-time Streaming Pipeline.

Covers:
  - TranscriptChunk dataclass
  - MockStreamingASR: produces chunks, is_final flag, close()
  - StreamingPipeline: process() yields StreamingResult, feed_audio() helper
  - WebSocket /ws/stream endpoint end-to-end

Rule §0: no external APIs — MockStreamingASR only, DB mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── TranscriptChunk ───────────────────────────────────────────────────────────


class TestTranscriptChunk:
    def test_basic_creation(self):
        from temporalos.audio.streaming import TranscriptChunk

        chunk = TranscriptChunk(text="hello world", start_ms=0, end_ms=1000)
        assert chunk.text == "hello world"
        assert chunk.start_ms == 0
        assert chunk.end_ms == 1000
        assert not chunk.is_final

    def test_final_chunk(self):
        from temporalos.audio.streaming import TranscriptChunk

        chunk = TranscriptChunk(text="goodbye", start_ms=5000, end_ms=6000, is_final=True)
        assert chunk.is_final

    def test_words_default_empty(self):
        from temporalos.audio.streaming import TranscriptChunk

        chunk = TranscriptChunk(text="x", start_ms=0, end_ms=100)
        assert chunk.words == []


# ── MockStreamingASR ──────────────────────────────────────────────────────────


class TestMockStreamingASR:
    @pytest.mark.asyncio
    async def test_stream_produces_at_least_one_chunk(self):
        from temporalos.audio.streaming import MockStreamingASR

        asr = MockStreamingASR(words_per_second=3.0)
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(64_000))
        await q.put(None)
        result_q = await asr.stream(q)
        chunks = []
        while True:
            chunk = await asyncio.wait_for(result_q.get(), timeout=5.0)
            if chunk is None:
                break
            chunks.append(chunk)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_final_chunk_emitted(self):
        from temporalos.audio.streaming import MockStreamingASR

        asr = MockStreamingASR()
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(32_000))
        await q.put(None)
        result_q = await asr.stream(q)
        final_seen = False
        while True:
            chunk = await asyncio.wait_for(result_q.get(), timeout=5.0)
            if chunk is None:
                break
            if chunk.is_final:
                final_seen = True
        assert final_seen

    @pytest.mark.asyncio
    async def test_chunks_have_words(self):
        from temporalos.audio.streaming import MockStreamingASR

        asr = MockStreamingASR(words_per_second=5.0)
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(64_000))
        await q.put(None)
        result_q = await asr.stream(q)
        while True:
            chunk = await asyncio.wait_for(result_q.get(), timeout=5.0)
            if chunk is None:
                break
            assert isinstance(chunk.words, list)

    @pytest.mark.asyncio
    async def test_close_sets_flag(self):
        from temporalos.audio.streaming import MockStreamingASR

        asr = MockStreamingASR()
        assert not asr._closed
        await asr.close()
        assert asr._closed

    def test_factory_returns_mock(self):
        from temporalos.audio.streaming import MockStreamingASR, get_streaming_asr

        assert isinstance(get_streaming_asr("mock"), MockStreamingASR)

    def test_factory_unknown_falls_back_to_mock(self):
        from temporalos.audio.streaming import MockStreamingASR, get_streaming_asr

        assert isinstance(get_streaming_asr("nonexistent_backend"), MockStreamingASR)


# ── StreamingPipeline ─────────────────────────────────────────────────────────


class TestStreamingPipeline:
    @pytest.mark.asyncio
    async def test_process_yields_streaming_results(self):
        from temporalos.audio.streaming import MockStreamingASR
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline(asr=MockStreamingASR(words_per_second=5.0))
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(32_000))
        await q.put(None)
        results = [r async for r in pipeline.process(q)]
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_result_has_transcript_string(self):
        from temporalos.audio.streaming import MockStreamingASR
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline(asr=MockStreamingASR())
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(32_000))
        await q.put(None)
        async for r in pipeline.process(q):
            assert isinstance(r.transcript, str)
            break

    @pytest.mark.asyncio
    async def test_result_has_timestamp_ms(self):
        from temporalos.audio.streaming import MockStreamingASR
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline(asr=MockStreamingASR())
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(32_000))
        await q.put(None)
        async for r in pipeline.process(q):
            assert isinstance(r.timestamp_ms, int)
            break

    @pytest.mark.asyncio
    async def test_last_result_is_final(self):
        from temporalos.audio.streaming import MockStreamingASR
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline(asr=MockStreamingASR())
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(32_000))
        await q.put(None)
        results = [r async for r in pipeline.process(q)]
        assert results[-1].is_final

    @pytest.mark.asyncio
    async def test_feed_audio_sends_chunk_and_sentinel(self):
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        q: asyncio.Queue = asyncio.Queue()
        await pipeline.feed_audio(q, b"pcm data", final=True)
        chunk = await q.get()
        sentinel = await q.get()
        assert chunk == b"pcm data"
        assert sentinel is None

    @pytest.mark.asyncio
    async def test_tiny_audio_does_not_crash(self):
        from temporalos.audio.streaming import MockStreamingASR
        from temporalos.pipeline.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline(asr=MockStreamingASR())
        q: asyncio.Queue = asyncio.Queue()
        await q.put(bytes(100))
        await q.put(None)
        results = [r async for r in pipeline.process(q)]
        # Must complete without exception
        assert isinstance(results, list)


# ── WebSocket streaming endpoint ──────────────────────────────────────────────


class TestStreamingWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("temporalos.db.session.init_db", return_value=None):
            from temporalos.api.main import app

            self.client = TestClient(app)
            yield

    def test_connect_send_end_receive_done(self):
        with self.client.websocket_connect("/ws/stream") as ws:
            ws.send_json({"type": "end"})
            received = []
            for _ in range(20):  # read up to 20 messages
                msg = ws.receive_json()
                received.append(msg)
                if msg.get("type") == "done":
                    break
            types = {m["type"] for m in received}
            assert "done" in types or "result" in types

    def test_connect_send_audio_bytes_and_end(self):
        with self.client.websocket_connect("/ws/stream") as ws:
            ws.send_bytes(bytes(1024))
            ws.send_json({"type": "end"})
            msg = ws.receive_json()
            assert msg.get("type") in ("result", "done")

    def test_session_id_in_messages(self):
        with self.client.websocket_connect("/ws/stream") as ws:
            ws.send_json({"type": "end"})
            msg = ws.receive_json()
            assert "session_id" in msg
