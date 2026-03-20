"""
Local SLM pipeline — Phase 5.

Full end-to-end video → structured intelligence with zero external API calls.
Uses: faster-whisper (audio) + Qwen2.5-VL (vision) + fine-tuned model (extraction).
Designed to run on an M-series Mac (16 GB RAM) or any CUDA GPU.

Benchmark target (Phase 5):
  - Accuracy within 5 % F1 of GPT-4o baseline
  - < 3× wall-clock time vs API pipeline on equivalent hardware
  - $0.00 per video (no API costs)

Usage (Phase 5):
  pipeline = LocalPipeline.from_settings()
  result = pipeline.process("call.mp4")
  print(result.to_dict())
"""

from __future__ import annotations


class LocalPipeline:
    """
    Phase 5 — Local SLM Pipeline.

    Composes:
      1. faster-whisper (audio transcription, already used in Phase 1)
      2. Qwen2.5-VL-7B-Instruct (vision analysis, added in Phase 2)
      3. Fine-tuned Mistral-7B-Instruct (extraction, trained in Phase 4)

    All models run locally via HuggingFace transformers / llama.cpp.
    """

    def __init__(
        self,
        whisper_model: str = "large-v3",
        vision_model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct",
        extraction_model_path: str = "",  # path to fine-tuned adapter
    ) -> None:
        self._whisper_model = whisper_model
        self._vision_model_id = vision_model_id
        self._extraction_model_path = extraction_model_path

    @classmethod
    def from_settings(cls) -> "LocalPipeline":
        from ...config import get_settings  # type: ignore[import]

        s = get_settings()
        return cls(whisper_model=s.audio.whisper_model)

    # Phase 5 TODO: implement process()
    def process(self, video_path: str) -> object:
        raise NotImplementedError("LocalPipeline.process() — Phase 5")
