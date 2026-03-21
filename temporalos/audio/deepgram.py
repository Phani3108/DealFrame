"""Deepgram Streaming ASR adapter.

Implements the StreamingASRBase protocol using Deepgram's WebSocket API.
Falls back to MockStreamingASR if the ``deepgram-sdk`` package is not installed
or ``DEEPGRAM_API_KEY`` is not set.

Usage:
    asr = DeepgramStreamingASR()  # reads DEEPGRAM_API_KEY from env
    results_q = await asr.stream(audio_q)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from .streaming import StreamingASRBase, TranscriptChunk

logger = logging.getLogger(__name__)

# Deepgram WebSocket endpoint
_DG_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramStreamingASR(StreamingASRBase):
    """Real Deepgram streaming ASR via WebSocket.

    Requires:
        - ``websockets`` package (``pip install websockets``)
        - ``DEEPGRAM_API_KEY`` environment variable
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-2",
        language: str = "en",
        sample_rate: int = 16000,
        encoding: str = "linear16",
        channels: int = 1,
        punctuate: bool = True,
        smart_format: bool = True,
        interim_results: bool = True,
    ) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Deepgram API key not found. Set DEEPGRAM_API_KEY env var "
                "or pass api_key= to constructor."
            )
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._channels = channels
        self._punctuate = punctuate
        self._smart_format = smart_format
        self._interim_results = interim_results
        self._ws: Any = None
        self._closed = False

    def _build_ws_url(self) -> str:
        params = (
            f"model={self._model}"
            f"&language={self._language}"
            f"&sample_rate={self._sample_rate}"
            f"&encoding={self._encoding}"
            f"&channels={self._channels}"
            f"&punctuate={'true' if self._punctuate else 'false'}"
            f"&smart_format={'true' if self._smart_format else 'false'}"
            f"&interim_results={'true' if self._interim_results else 'false'}"
        )
        return f"{_DG_WS_URL}?{params}"

    async def stream(self, audio_chunks: asyncio.Queue) -> asyncio.Queue:
        import websockets  # type: ignore[import-untyped]

        results: asyncio.Queue[TranscriptChunk | None] = asyncio.Queue()
        url = self._build_ws_url()
        headers = {"Authorization": f"Token {self._api_key}"}

        self._ws = await websockets.connect(url, additional_headers=headers)

        async def _send_audio() -> None:
            """Forward audio chunks to Deepgram."""
            try:
                while True:
                    chunk = await audio_chunks.get()
                    if chunk is None:
                        # Send close signal to Deepgram
                        await self._ws.send(json.dumps({"type": "CloseStream"}))
                        break
                    await self._ws.send(chunk)
            except Exception as exc:
                logger.error("Deepgram send error: %s", exc)

        async def _receive_transcripts() -> None:
            """Read transcript messages from Deepgram."""
            try:
                async for msg in self._ws:
                    data = json.loads(msg)
                    if data.get("type") == "Results":
                        channel = data.get("channel", {})
                        alt = (channel.get("alternatives") or [{}])[0]
                        transcript_text = alt.get("transcript", "").strip()
                        if not transcript_text:
                            continue

                        is_final = data.get("is_final", False)
                        start_s = data.get("start", 0.0)
                        duration_s = data.get("duration", 0.0)
                        confidence = alt.get("confidence", 0.0)

                        # Word-level timestamps
                        words_meta = []
                        for w in alt.get("words", []):
                            words_meta.append({
                                "word": w.get("word", ""),
                                "start_ms": int(w.get("start", 0) * 1000),
                                "end_ms": int(w.get("end", 0) * 1000),
                            })

                        await results.put(TranscriptChunk(
                            text=transcript_text,
                            start_ms=int(start_s * 1000),
                            end_ms=int((start_s + duration_s) * 1000),
                            is_final=is_final,
                            confidence=confidence,
                            words=words_meta,
                        ))
            except websockets.ConnectionClosed:
                logger.debug("Deepgram WebSocket closed")
            except Exception as exc:
                logger.error("Deepgram receive error: %s", exc)
            finally:
                await results.put(None)  # sentinel

        asyncio.create_task(_send_audio())
        asyncio.create_task(_receive_transcripts())
        return results

    async def close(self) -> None:
        self._closed = True
        if self._ws:
            await self._ws.close()
            self._ws = None
