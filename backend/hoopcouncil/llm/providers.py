"""LLM provider abstraction: Anthropic, OpenAI, Gemini, local (OpenAI-compatible, e.g. Ollama) and mock.

All providers are called over plain HTTPS with httpx so no vendor SDK is required.
Model defaults are tiered: player agents use an inexpensive model, the coach a stronger one.
Override with HOOP_PLAYER_MODEL / HOOP_COACH_MODEL.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field

from .. import config

DEFAULT_MODELS = {
    # provider: (cheap tier for player agents, stronger tier for the coach)
    "anthropic": ("claude-haiku-4-5-20251001", "claude-sonnet-5-5"),
    "openai": ("gpt-4.1-mini", "gpt-4.1"),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro"),
    "local": ("llama3.1", "llama3.1"),
    "mock": ("mock-player", "mock-coach"),
}


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    usage: dict = field(default_factory=dict)


class LLMProvider:
    name = "base"

    def __init__(self, model: str, temperature: float | None = None, max_tokens: int | None = None):
        self.model = model
        self.temperature = config.LLM_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.LLM_MAX_TOKENS

    async def complete(self, system: str, user: str, meta: dict | None = None) -> LLMResult:
        raise NotImplementedError

    async def _post(self, url, payload, headers, retries=3):
        import httpx

        last = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    r = await client.post(url, json=payload, headers=headers)
                if r.status_code in (429, 500, 502, 503, 529):
                    last = RuntimeError(f"{self.name} HTTP {r.status_code}: {r.text[:300]}")
                    await asyncio.sleep(2 ** attempt * 2)
                    continue
                if r.status_code >= 400:
                    raise RuntimeError(f"{self.name} HTTP {r.status_code}: {r.text[:500]}")
                return r.json()
            except httpx.TransportError as e:  # network blip
                last = e
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"{self.name} request failed after {retries} attempts: {last}")


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    async def complete(self, system, user, meta=None):
        t = time.monotonic()
        data = await self._post(
            "https://api.anthropic.com/v1/messages",
            {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature, "system": system,
             "messages": [{"role": "user", "content": user}]},
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
             "content-type": "application/json"})
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return LLMResult(text, data.get("model", self.model), int((time.monotonic() - t) * 1000), data.get("usage", {}))


class OpenAIProvider(LLMProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"

    def _key(self):
        return os.environ["OPENAI_API_KEY"]

    async def complete(self, system, user, meta=None):
        t = time.monotonic()
        headers = {"content-type": "application/json"}
        k = self._key()
        if k:
            headers["Authorization"] = f"Bearer {k}"
        payload = {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "response_format": {"type": "json_object"}}
        data = await self._post(f"{self.base_url}/chat/completions", payload, headers)
        text = data["choices"][0]["message"]["content"] or ""
        return LLMResult(text, data.get("model", self.model), int((time.monotonic() - t) * 1000), data.get("usage", {}))


class LocalProvider(OpenAIProvider):
    """Any OpenAI-compatible local server (Ollama, LM Studio, vLLM)."""
    name = "local"

    @property
    def base_url(self):
        return config.LOCAL_LLM_BASE_URL.rstrip("/")

    def _key(self):
        return os.environ.get("HOOP_LOCAL_LLM_API_KEY", "")


class GeminiProvider(LLMProvider):
    name = "gemini"

    async def complete(self, system, user, meta=None):
        t = time.monotonic()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
               f"?key={os.environ['GEMINI_API_KEY']}")
        payload = {"systemInstruction": {"parts": [{"text": system}]},
                   "contents": [{"role": "user", "parts": [{"text": user}]}],
                   "generationConfig": {"temperature": self.temperature, "maxOutputTokens": self.max_tokens,
                                        "responseMimeType": "application/json"}}
        data = await self._post(url, payload, {"content-type": "application/json"})
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        return LLMResult("".join(p.get("text", "") for p in parts), self.model, int((time.monotonic() - t) * 1000),
                         data.get("usageMetadata", {}))


class MockProvider(LLMProvider):
    """Offline provider for tests and UI development. Produces clearly-labelled placeholder
    JSON derived only from the supplied context (see agents/mock_logic.py)."""
    name = "mock"

    async def complete(self, system, user, meta=None):
        from ..agents.mock_logic import mock_response

        await asyncio.sleep(0.01)
        return LLMResult(json.dumps(mock_response(meta or {})), self.model, 10, {})


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "gemini": GeminiProvider,
             "local": LocalProvider, "mock": MockProvider}


def make_provider(provider: str | None = None, model: str | None = None, tier: str = "player") -> LLMProvider:
    provider = (provider or config.LLM_PROVIDER).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"unknown LLM provider {provider}; choose from {sorted(PROVIDERS)}")
    cheap, strong = DEFAULT_MODELS[provider]
    model = model or (config.PLAYER_MODEL if tier == "player" else config.COACH_MODEL) or (cheap if tier == "player" else strong)
    return PROVIDERS[provider](model=model, max_tokens=config.LLM_MAX_TOKENS if tier == "player" else max(config.LLM_MAX_TOKENS, 3500))
