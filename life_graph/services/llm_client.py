"""LM Studio + OpenRouter hybrid client — local embeddings, cloud synthesis.

Provides a unified client that routes:
  - Embeddings → LM Studio (local, free, private)
  - Extraction → LM Studio (local, fast for small models)
  - Synthesis  → OpenRouter (cloud, fast, high quality) when hybrid mode enabled

Falls back to fully local when OpenRouter is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.config import settings

logger = logging.getLogger(__name__)


class LMStudioClient:
    """Hybrid LLM client — local embeddings + optional cloud synthesis.

    When ``settings.use_hybrid_llm`` is True and an OpenRouter API key
    is configured, chat completions are routed to OpenRouter for speed.
    Embeddings always stay local via LM Studio.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url or settings.lm_studio_url
        self._api_key = api_key or settings.lm_studio_api_key
        self._client = None
        self._async_client = None
        self._cloud_client = None

    def _get_client(self):
        """Lazy-load synchronous OpenAI client (local)."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
            )
        return self._client

    def _get_async_client(self):
        """Lazy-load async OpenAI client (local)."""
        if self._async_client is None:
            from openai import AsyncOpenAI
            self._async_client = AsyncOpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
            )
        return self._async_client

    def _get_cloud_client(self):
        """Lazy-load async OpenAI client pointed at OpenRouter."""
        if self._cloud_client is None:
            from openai import AsyncOpenAI
            self._cloud_client = AsyncOpenAI(
                base_url=settings.openrouter_url,
                api_key=settings.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": "https://lifegraph.local",
                    "X-Title": "Life Graph",
                },
            )
        return self._cloud_client

    @property
    def _use_cloud(self) -> bool:
        """Whether to route synthesis to OpenRouter."""
        return settings.use_hybrid_llm and bool(settings.openrouter_api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat completion request.

        Routes to OpenRouter when hybrid mode is active,
        falls back to LM Studio on failure.
        """
        if self._use_cloud:
            result = await self._cloud_chat(messages, model, temperature, max_tokens, response_format)
            if result:
                return result
            logger.warning("OpenRouter failed, falling back to local LLM")

        return await self._local_chat(messages, model, temperature, max_tokens, response_format)

    async def _cloud_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        """Chat via OpenRouter (cloud)."""
        cloud_model = model or settings.openrouter_model
        client = self._get_cloud_client()

        kwargs: dict[str, Any] = {
            "model": cloud_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.info("OpenRouter chat OK (model=%s, len=%d)", cloud_model, len(content))
            return content
        except Exception:
            logger.exception("OpenRouter chat request failed (model=%s)", cloud_model)
            return ""

    async def _local_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        """Chat via LM Studio (local)."""
        model = model or settings.lm_synthesis_model
        client = self._get_async_client()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("LM Studio chat request failed (model=%s)", model)
            return ""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string (always local)."""
        client = self._get_async_client()
        model = settings.lm_embedding_model

        try:
            response = await client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding
        except Exception:
            logger.exception("LM Studio embedding failed (model=%s)", model)
            return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (always local)."""
        if not texts:
            return []

        client = self._get_async_client()
        model = settings.lm_embedding_model

        try:
            response = await client.embeddings.create(
                model=model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception:
            logger.exception("LM Studio batch embedding failed (model=%s)", model)
            return [[] for _ in texts]

    def list_models(self) -> list[str]:
        """List available models on the LM Studio server."""
        try:
            client = self._get_client()
            response = client.models.list()
            return [m.id for m in response.data]
        except Exception:
            logger.exception("Failed to list LM Studio models")
            return []
