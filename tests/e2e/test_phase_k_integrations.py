"""Phase K — Real Integrations & Production Streaming e2e tests.

Tests:
- Deepgram streaming ASR adapter (class exists, validates construction)
- S3/MinIO storage abstraction (local backend CRUD)
- Config consolidation (new settings sections)
- Streaming ASR factory (mock fallback)
"""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Deepgram Adapter ────────────────────────────────────────────────────────

class TestDeepgramASR:
    def test_module_importable(self):
        from temporalos.audio.deepgram import DeepgramStreamingASR
        assert DeepgramStreamingASR is not None

    def test_constructor_requires_api_key(self):
        # Remove env var if set
        old = os.environ.pop("DEEPGRAM_API_KEY", None)
        try:
            from temporalos.audio.deepgram import DeepgramStreamingASR
            with pytest.raises(ValueError, match="API key"):
                DeepgramStreamingASR()
        finally:
            if old:
                os.environ["DEEPGRAM_API_KEY"] = old

    def test_constructor_with_key(self):
        from temporalos.audio.deepgram import DeepgramStreamingASR
        asr = DeepgramStreamingASR(api_key="test-key-123")
        assert asr._api_key == "test-key-123"
        assert asr._model == "nova-2"

    def test_ws_url_construction(self):
        from temporalos.audio.deepgram import DeepgramStreamingASR
        asr = DeepgramStreamingASR(api_key="k", model="nova-2", language="en")
        url = asr._build_ws_url()
        assert "model=nova-2" in url
        assert "language=en" in url
        assert "sample_rate=16000" in url
        assert url.startswith("wss://api.deepgram.com")

    def test_inherits_base(self):
        from temporalos.audio.deepgram import DeepgramStreamingASR
        from temporalos.audio.streaming import StreamingASRBase
        assert issubclass(DeepgramStreamingASR, StreamingASRBase)


# ── Streaming Factory ───────────────────────────────────────────────────────

class TestStreamingFactory:
    def test_mock_fallback(self):
        from temporalos.audio.streaming import get_streaming_asr, MockStreamingASR
        asr = get_streaming_asr("mock")
        assert isinstance(asr, MockStreamingASR)

    def test_deepgram_without_key_falls_back(self):
        """Without DEEPGRAM_API_KEY, factory should fall back to mock."""
        old = os.environ.pop("DEEPGRAM_API_KEY", None)
        try:
            from temporalos.audio.streaming import get_streaming_asr, MockStreamingASR
            asr = get_streaming_asr("deepgram")
            assert isinstance(asr, MockStreamingASR)
        finally:
            if old:
                os.environ["DEEPGRAM_API_KEY"] = old

    def test_mock_produces_chunks(self):
        from temporalos.audio.streaming import MockStreamingASR, TranscriptChunk

        async def _test():
            asr = MockStreamingASR()
            audio_q: asyncio.Queue = asyncio.Queue()
            # Push some fake audio bytes (32000 = 1 second at 16kHz 16bit)
            await audio_q.put(b"\x00" * 32000)
            await audio_q.put(None)  # end

            results = await asr.stream(audio_q)
            chunks = []
            while True:
                c = await asyncio.wait_for(results.get(), timeout=5)
                if c is None:
                    break
                assert isinstance(c, TranscriptChunk)
                chunks.append(c)

            assert len(chunks) > 0
            assert chunks[-1].is_final

        _run(_test())


# ── Storage Layer ────────────────────────────────────────────────────────────

class TestLocalStorage:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from temporalos.storage import LocalStorage, reset_storage
        reset_storage()
        self.storage = LocalStorage(base_dir=str(tmp_path / "storage"))
        self.tmp_path = tmp_path

    def test_put_and_get(self):
        async def _test():
            uri = await self.storage.put("test/file.txt", b"hello world")
            assert "file.txt" in uri
            data = await self.storage.get("test/file.txt")
            assert data == b"hello world"
        _run(_test())

    def test_exists(self):
        async def _test():
            assert not await self.storage.exists("nope.txt")
            await self.storage.put("nope.txt", b"x")
            assert await self.storage.exists("nope.txt")
        _run(_test())

    def test_delete(self):
        async def _test():
            await self.storage.put("del.txt", b"x")
            assert await self.storage.delete("del.txt")
            assert not await self.storage.exists("del.txt")
            assert not await self.storage.delete("nonexistent.txt")
        _run(_test())

    def test_list_keys(self):
        async def _test():
            await self.storage.put("a/1.txt", b"x")
            await self.storage.put("a/2.txt", b"x")
            await self.storage.put("b/3.txt", b"x")
            all_keys = await self.storage.list_keys()
            assert len(all_keys) == 3
            a_keys = await self.storage.list_keys("a")
            assert len(a_keys) == 2
        _run(_test())

    def test_path_traversal_blocked(self):
        async def _test():
            with pytest.raises(ValueError, match="Invalid key"):
                await self.storage.put("../../etc/passwd", b"bad")
        _run(_test())

    def test_binary_data(self):
        async def _test():
            data = bytes(range(256)) * 100
            await self.storage.put("binary.bin", data)
            retrieved = await self.storage.get("binary.bin")
            assert retrieved == data
        _run(_test())


class TestStorageFactory:
    def test_default_local(self):
        from temporalos.storage import get_storage, LocalStorage, reset_storage
        reset_storage()
        os.environ.pop("STORAGE_BACKEND", None)
        s = get_storage()
        assert isinstance(s, LocalStorage)
        reset_storage()

    def test_singleton(self):
        from temporalos.storage import get_storage, reset_storage
        reset_storage()
        a = get_storage()
        b = get_storage()
        assert a is b
        reset_storage()


# ── Config Consolidation ────────────────────────────────────────────────────

class TestConfigConsolidation:
    def test_storage_settings(self):
        from temporalos.config import StorageSettings
        s = StorageSettings()
        assert s.backend == "local"
        assert s.s3_bucket == "temporalos"

    def test_deepgram_settings(self):
        from temporalos.config import DeepgramSettings
        d = DeepgramSettings()
        assert d.model == "nova-2"
        assert d.language == "en"
        assert d.api_key == ""

    def test_integration_settings(self):
        from temporalos.config import IntegrationSettings
        i = IntegrationSettings()
        assert i.deepgram_api_key == ""
        assert i.salesforce_client_id == ""
        assert i.notion_api_key == ""
        assert i.zapier_hook_secret == ""

    def test_settings_has_new_sections(self):
        from temporalos.config import Settings
        s = Settings(database_url="sqlite+aiosqlite:///test.db")
        assert hasattr(s, 'storage')
        assert hasattr(s, 'deepgram')
        assert hasattr(s, 'integrations')
        assert s.storage.backend == "local"
        assert s.deepgram.model == "nova-2"

    def test_effective_database_url(self):
        from temporalos.config import Settings
        s = Settings(database_url="sqlite+aiosqlite:///custom.db")
        assert s.effective_database_url == "sqlite+aiosqlite:///custom.db"


# ── Integration Modules ─────────────────────────────────────────────────────

class TestIntegrationModules:
    def test_salesforce_importable(self):
        import temporalos.integrations.salesforce as m
        assert hasattr(m, 'create_task') and hasattr(m, 'sync_job')

    def test_hubspot_importable(self):
        import temporalos.integrations.hubspot as m
        assert hasattr(m, 'create_note_engagement') and hasattr(m, 'sync_job')

    def test_slack_importable(self):
        import temporalos.integrations.slack as m
        assert hasattr(m, 'verify_slack_signature') or hasattr(m, 'parse_slash_command')

    def test_zoom_importable(self):
        import temporalos.integrations.zoom as m
        assert hasattr(m, 'verify_zoom_signature') or hasattr(m, 'parse_recording_event')

    def test_notion_importable(self):
        import temporalos.integrations.notion as m
        assert hasattr(m, 'create_page') and hasattr(m, 'list_databases')

    def test_zapier_importable(self):
        from temporalos.integrations.zapier import ZapierSubscriptionManager
        assert ZapierSubscriptionManager is not None

    def test_langchain_tool_importable(self):
        from temporalos.integrations.langchain_tool import TemporalOSTool
        assert TemporalOSTool is not None

    def test_llamaindex_reader_importable(self):
        from temporalos.integrations.llamaindex_reader import TemporalOSReader
        assert TemporalOSReader is not None

    def test_zoom_oauth_importable(self):
        from temporalos.integrations.zoom_oauth import ZoomOAuth
        assert ZoomOAuth is not None

    def test_slack_oauth_importable(self):
        from temporalos.integrations.slack_oauth import SlackOAuth
        assert SlackOAuth is not None
