"""
Fine-tuned extraction model adapter — Phase 4.

Drop-in replacement for GPT-4o or Claude extraction adapters.
Loads a locally fine-tuned Mistral/Llama model + LoRA adapter and
runs structured extraction with zero API calls.

Falls back to a simple rule-based stub when:
  - No adapter_path is configured
  - transformers / torch are not installed (CPU-only / CI environments)

Usage:
    model = FineTunedExtractionModel.from_settings()
    result = model.extract(segment)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ...core.types import AlignedSegment, ExtractionResult
from ...observability.telemetry import get_tracer
from ..base import BaseExtractionModel

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a sales intelligence analyst. Given a segment from a sales call "
    "(optional screenshot + transcript), extract structured decision intelligence. "
    "Be precise and evidence-based. Only include objections and decision signals "
    "that are clearly stated or strongly implied in the provided content. "
    "Respond ONLY with valid JSON — no prose, no markdown fences."
)

_INPUT_TEMPLATE = """\
Timestamp: {timestamp}

Transcript:
{transcript}

Visual context: {visual_context}
"""

_DEFAULT_OUTPUT = {
    "topic": "other",
    "sentiment": "neutral",
    "risk": "low",
    "risk_score": 0.1,
    "objections": [],
    "decision_signals": [],
    "confidence": 0.0,
}


class FineTunedExtractionModel(BaseExtractionModel):
    """
    Local fine-tuned extraction adapter.

    Lazy-loads model + tokenizer on first call to extract() to keep import
    time fast. If the model cannot be loaded, falls back to a stub that
    returns a low-confidence default ExtractionResult so the rest of the
    pipeline can continue.
    """

    name = "finetuned"

    def __init__(
        self,
        adapter_path: str = "",
        max_new_tokens: int = 512,
        temperature: float = 0.0,
    ) -> None:
        self._adapter_path = adapter_path
        self._max_new_tokens = max_new_tokens
        self._temperature = temperature
        self._model = None
        self._tokenizer = None
        self._available: bool | None = None  # None = not tried yet

    @classmethod
    def from_settings(cls) -> "FineTunedExtractionModel":
        from ...config import get_settings
        s = get_settings().finetuning
        return cls(adapter_path=s.adapter_path)

    # ── BaseExtractionModel interface ─────────────────────────────────────────

    def extract(self, segment: AlignedSegment) -> ExtractionResult:
        tracer = get_tracer()
        start = time.time()

        with tracer.start_as_current_span("finetuned.extract") as span:
            span.set_attribute("extraction.model", self.name)
            span.set_attribute("extraction.adapter_path", self._adapter_path or "none")

            transcript = " ".join(w.text for w in segment.words)
            prompt = self._build_prompt(segment.timestamp_ms, transcript)

            payload = self._infer(prompt)

            latency_ms = int((time.time() - start) * 1000)
            span.set_attribute("extraction.latency_ms", latency_ms)
            span.set_attribute("extraction.confidence", payload.get("confidence", 0.0))

            return ExtractionResult(
                topic=str(payload.get("topic", "other")),
                sentiment=str(payload.get("sentiment", "neutral")),
                risk=str(payload.get("risk", "low")),
                risk_score=float(payload.get("risk_score", 0.0)),
                objections=list(payload.get("objections") or []),
                decision_signals=list(payload.get("decision_signals") or []),
                confidence=float(payload.get("confidence", 0.0)),
                model_name=self.name,
                latency_ms=latency_ms,
            )

    @property
    def is_available(self) -> bool:
        """True if the adapter_path exists and required packages are installed."""
        if self._available is None:
            self._available = bool(
                self._adapter_path
                and Path(self._adapter_path).exists()
                and self._try_import()
            )
        return self._available

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_prompt(self, timestamp_ms: int, transcript: str) -> str:
        seconds = timestamp_ms // 1000
        ts = f"{seconds // 60:02d}:{seconds % 60:02d}"
        return (
            f"[INST] {_SYSTEM_PROMPT}\n\n"
            + _INPUT_TEMPLATE.format(
                timestamp=ts,
                transcript=transcript or "(no transcript)",
                visual_context="No visual context available.",
            )
            + " [/INST]\n"
        )

    def _infer(self, prompt: str) -> dict:
        if not self.is_available:
            return dict(_DEFAULT_OUTPUT)

        try:
            self._ensure_loaded()
            inputs = self._tokenizer(  # type: ignore[misc]
                prompt, return_tensors="pt", truncation=True, max_length=1024
            ).to(self._model.device)  # type: ignore[union-attr]

            outputs = self._model.generate(  # type: ignore[union-attr]
                **inputs,
                max_new_tokens=self._max_new_tokens,
                temperature=self._temperature if self._temperature > 0 else None,
                do_sample=self._temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,  # type: ignore[misc]
            )
            generated = self._tokenizer.decode(  # type: ignore[misc]
                outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            )
            return _parse_json(generated)
        except Exception:
            return dict(_DEFAULT_OUTPUT)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self._adapter_path)
        base_model = AutoModelForCausalLM.from_pretrained(
            self._adapter_path,
            device_map="auto",
            torch_dtype=torch.float16,
        )
        self._model = PeftModel.from_pretrained(base_model, self._adapter_path)
        self._model.eval()

    @staticmethod
    def _try_import() -> bool:
        try:
            import peft  # noqa: F401
            import torch  # noqa: F401
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """Extract JSON from model output, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return dict(_DEFAULT_OUTPUT)
