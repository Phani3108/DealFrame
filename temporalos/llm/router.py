"""LLM Provider abstraction — route to OpenAI, Anthropic, or Ollama.

Usage:
    from temporalos.llm.router import get_llm
    llm = get_llm()
    result = await llm.complete("Summarize this call.", system="You are an analyst.")
    result = await llm.complete_json("Extract fields.", schema={...})
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = None


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


class BaseLLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_json: bool = False,
    ) -> LLMResponse: ...

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        resp = await self.complete(prompt, system, temperature, max_tokens, response_json=True)
        text = resp.text.strip()
        # Strip markdown fences if model wraps output
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text)

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]: ...


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, api_key: str = "", model: str = "gpt-4o", max_tokens: int = 2048):
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key

    def _get_client(self):
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=self._api_key or None)
        except ImportError:
            raise RuntimeError("pip install openai")

    async def complete(self, prompt, system="", temperature=0.0,
                       max_tokens=2048, response_json=False) -> LLMResponse:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        t0 = time.monotonic()
        kwargs: Dict[str, Any] = dict(
            model=self._model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        latency = int((time.monotonic() - t0) * 1000)
        choice = resp.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=self._model,
            latency_ms=latency,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            raw=resp,
        )

    async def stream(self, prompt, system="", temperature=0.0, max_tokens=2048):
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        stream = await client.chat.completions.create(
            model=self._model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str = "", model: str = "claude-sonnet-4-5", max_tokens: int = 2048):
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key

    def _get_client(self):
        try:
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=self._api_key or None)
        except ImportError:
            raise RuntimeError("pip install anthropic")

    async def complete(self, prompt, system="", temperature=0.0,
                       max_tokens=2048, response_json=False) -> LLMResponse:
        client = self._get_client()
        t0 = time.monotonic()
        resp = await client.messages.create(
            model=self._model, max_tokens=max_tokens,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        latency = int((time.monotonic() - t0) * 1000)
        text = resp.content[0].text if resp.content else ""
        return LLMResponse(
            text=text, model=self._model, latency_ms=latency,
            prompt_tokens=resp.usage.input_tokens if resp.usage else 0,
            completion_tokens=resp.usage.output_tokens if resp.usage else 0,
            raw=resp,
        )

    async def stream(self, prompt, system="", temperature=0.0, max_tokens=2048):
        client = self._get_client()
        async with client.messages.stream(
            model=self._model, max_tokens=max_tokens,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def complete(self, prompt, system="", temperature=0.0,
                       max_tokens=2048, response_json=False) -> LLMResponse:
        import aiohttp
        t0 = time.monotonic()
        payload = {
            "model": self._model, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        if response_json:
            payload["format"] = "json"
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self._base_url}/api/generate", json=payload) as resp:
                data = await resp.json()
        latency = int((time.monotonic() - t0) * 1000)
        return LLMResponse(
            text=data.get("response", ""), model=self._model,
            latency_ms=latency, raw=data,
        )

    async def stream(self, prompt, system="", temperature=0.0, max_tokens=2048):
        import aiohttp
        payload = {
            "model": self._model, "prompt": prompt, "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self._base_url}/api/generate", json=payload) as resp:
                async for line in resp.content:
                    if line:
                        data = json.loads(line)
                        if data.get("response"):
                            yield data["response"]


class MockLLMProvider(BaseLLMProvider):
    """For tests / offline mode — returns rule-based responses."""
    name = "mock"

    def __init__(self, default_response: str = ""):
        self._default = default_response

    async def complete(self, prompt, system="", temperature=0.0,
                       max_tokens=2048, response_json=False) -> LLMResponse:
        if response_json:
            if self._default:
                text = self._default
            else:
                text = json.dumps({
                    "topic": "general", "sentiment": "neutral", "risk": "low",
                    "risk_score": 0.2, "objections": [], "decision_signals": [],
                    "confidence": 0.5, "summary": "Mock LLM response."
                })
        else:
            text = self._default or f"Mock response to: {prompt[:100]}"
        return LLMResponse(text=text, model="mock", latency_ms=1)

    async def stream(self, prompt, system="", temperature=0.0, max_tokens=2048):
        text = self._default or f"Mock response to: {prompt[:100]}"
        for word in text.split():
            yield word + " "


# ── Router / Factory ──────────────────────────────────────────────────────────

_provider: Optional[BaseLLMProvider] = None


def get_llm(provider: Optional[str] = None) -> BaseLLMProvider:
    """Get the configured LLM provider. Caches singleton."""
    global _provider
    if _provider is not None and provider is None:
        return _provider

    from ..config import get_settings
    s = get_settings()
    name = provider or s.temporalos_mode

    if name == "local" or (not s.openai_api_key and not s.anthropic_api_key):
        # Try Ollama, fallback to mock
        _provider = OllamaProvider()
        logger.info("LLM provider: ollama (local)")
    elif s.openai_api_key:
        _provider = OpenAIProvider(api_key=s.openai_api_key, model=s.openai.model)
        logger.info("LLM provider: openai (%s)", s.openai.model)
    elif s.anthropic_api_key:
        _provider = AnthropicProvider(api_key=s.anthropic_api_key, model=s.anthropic.model)
        logger.info("LLM provider: anthropic (%s)", s.anthropic.model)
    else:
        _provider = MockLLMProvider()
        logger.info("LLM provider: mock (no API keys)")
    return _provider


def set_llm(provider: BaseLLMProvider) -> None:
    """Override the LLM provider (for testing)."""
    global _provider
    _provider = provider
