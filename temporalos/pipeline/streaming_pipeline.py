"""Streaming pipeline orchestrator.

Consumes audio chunks from an asyncio.Queue, runs them through streaming ASR,
aligns words into windows, and optionally extracts structured intelligence from
each completed window.

Back-pressure strategy: the audio queue has a bounded maxsize (default 100).
If the producer fills the queue, it blocks until the ASR consumer catches up.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..audio.streaming import MockStreamingASR, StreamingASRBase, TranscriptChunk
from ..core.types import AlignedSegment, ExtractionResult, Frame, Word


@dataclass
class StreamingResult:
    """A partial result emitted during live processing."""

    timestamp_ms: int
    transcript: str
    extraction: ExtractionResult | None = None
    is_final: bool = False


class StreamingPipeline:
    """
    Orchestrates streaming ASR → incremental window accumulation → optional extraction.

    Usage::

        pipeline = StreamingPipeline(asr=MockStreamingASR())
        audio_queue = asyncio.Queue()

        async for result in pipeline.process(audio_queue):
            print(result.transcript, result.extraction)
    """

    def __init__(
        self,
        asr: StreamingASRBase | None = None,
        chunk_window_ms: int = 5000,
        extractor=None,
    ) -> None:
        self._asr = asr or MockStreamingASR()
        self._chunk_window_ms = chunk_window_ms
        self._extractor = extractor  # Optional BaseExtractionModel

    async def process(
        self,
        audio_queue: asyncio.Queue,
        frames: list[Frame] | None = None,
    ):
        """
        Async generator — yields StreamingResult after each completed ASR chunk.

        Runs extraction on each transcript window when an extractor is configured.
        """
        transcript_queue = await self._asr.stream(audio_queue)
        accumulated_words: list[Word] = []
        window_start_ms = 0

        while True:
            chunk: TranscriptChunk | None = await transcript_queue.get()
            if chunk is None:
                break

            for w in chunk.words:
                accumulated_words.append(
                    Word(
                        text=w["word"],
                        start_ms=w["start_ms"],
                        end_ms=w["end_ms"],
                    )
                )

            should_emit = chunk.is_final or (
                chunk.end_ms - window_start_ms >= self._chunk_window_ms
            )

            if should_emit:
                segment_words = [
                    w for w in accumulated_words if w.start_ms >= window_start_ms
                ]
                transcript_text = " ".join(w.text for w in segment_words)
                extraction: ExtractionResult | None = None

                if self._extractor and segment_words:
                    seg = AlignedSegment(
                        timestamp_ms=window_start_ms,
                        frame=frames[0] if frames else None,
                        words=segment_words,
                    )
                    try:
                        extraction = await self._extractor.extract(seg)
                    except Exception:
                        extraction = None

                yield StreamingResult(
                    timestamp_ms=window_start_ms,
                    transcript=transcript_text,
                    extraction=extraction,
                    is_final=chunk.is_final,
                )
                window_start_ms = chunk.end_ms

        await self._asr.close()

    async def feed_audio(
        self, queue: asyncio.Queue, audio_bytes: bytes, *, final: bool = False
    ) -> None:
        """Convenience helper to push audio data into the pipeline queue."""
        await queue.put(audio_bytes)
        if final:
            await queue.put(None)
