"""Whisper-based batch speech-to-text transcription with word-level timestamps."""

from __future__ import annotations

from ..core.types import Word
from ..observability.telemetry import get_tracer

# Model cache — avoid reloading the large model on every request
_model_cache: dict[str, object] = {}


def _get_model(model_name: str) -> object:
    if model_name not in _model_cache:
        # faster-whisper is the default backend (much faster than openai-whisper)
        from faster_whisper import WhisperModel  # type: ignore[import]

        _model_cache[model_name] = WhisperModel(
            model_name,
            device="auto",       # cuda > mps > cpu
            compute_type="auto", # fp16 on GPU, int8 on CPU
        )
    return _model_cache[model_name]


def transcribe(
    video_path: str,
    model_name: str = "large-v3",
    language: str | None = None,
) -> list[Word]:
    """
    Transcribe audio from `video_path` and return word-level timestamped output.
    Uses faster-whisper for significantly reduced latency vs the original Whisper.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("audio.transcribe") as span:
        span.set_attribute("audio.model", model_name)
        span.set_attribute("audio.video_path", video_path)

        model = _get_model(model_name)

        transcribe_opts: dict = {"word_timestamps": True}
        if language:
            transcribe_opts["language"] = language

        segments, _ = model.transcribe(video_path, **transcribe_opts)  # type: ignore[union-attr]

        words: list[Word] = []
        for segment in segments:
            for word_data in segment.words or []:
                words.append(
                    Word(
                        text=word_data.word.strip(),
                        start_ms=int(word_data.start * 1000),
                        end_ms=int(word_data.end * 1000),
                        speaker=None,  # diarization handled separately
                    )
                )

        span.set_attribute("audio.words_extracted", len(words))
        return words
