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


def get_resilient_llm():
    """Return the resilient LLM singleton.

    Imported lazily (call time, not module load time) because
    ``life_graph.api.dependencies`` imports ``LMStudioClient`` at module
    scope — a top-level import here would create a circular import.
    """
    from life_graph.api.dependencies import get_resilient_llm as _get_resilient_llm

    return _get_resilient_llm()


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

        Routes to the resilient cloud chain (OpenRouter + fallbacks) when
        hybrid mode is active, falling back to local LM Studio when the
        cloud chain is exhausted.
        """
        if self._use_cloud:
            try:
                return await self._cloud_chat(
                    messages, model, temperature, max_tokens, response_format
                )
            except Exception:
                logger.warning(
                    "Resilient cloud chat exhausted, falling back to local LLM",
                    exc_info=True,
                )

        return await self._local_chat(messages, model, temperature, max_tokens, response_format)

    async def chat_local_only(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format: dict | None = None,
    ) -> str:
        """Chat on the local runtime only — never routed to a cloud chain.

        ``chat()`` sends to OpenRouter when hybrid mode is on. Callers holding
        personal data that must not leave the machine (mail bodies) use this.
        Returns "" on failure, like ``chat()``.
        """
        return await self._local_chat(messages, model, temperature, max_tokens, response_format)

    async def _cloud_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        """Chat via the resilient cloud chain (OpenRouter/Gemini/... with failover)."""
        return await get_resilient_llm().chat(
            messages,
            model=model,  # None -> wrapper picks the tier default
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    async def _local_chat(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        """Chat via the local runtime (Ollama's native API, or LM Studio's /v1)."""
        model = model or settings.lm_synthesis_model
        if self._is_ollama:
            return await self._ollama_chat(
                messages, model, temperature, max_tokens, response_format
            )
        client = self._get_async_client()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if settings.lm_reasoning_effort:
            # Thinking models (e.g. Qwen3 on Ollama) otherwise spend the whole
            # max_tokens budget reasoning and return empty content, which the
            # extractor silently treats as "no facts". Sent via extra_body so
            # an SDK-side enum can't reject values like "none".
            kwargs["extra_body"] = {"reasoning_effort": settings.lm_reasoning_effort}

        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("LM Studio chat request failed (model=%s)", model)
            return ""

    # ── Ollama's native API ───────────────────────────────────
    #
    # Ollama's OpenAI-style /v1 ignores num_ctx and keep_alive (measured
    # 2026-10-22): a /v1 call loaded qwen3:14b at the shared 32k context
    # (14.4 GB) beside Jarvis's 16k copy, and let it go after 5 minutes. The
    # native API takes both (services/local_runtime.py).

    @property
    def _is_ollama(self) -> bool:
        from life_graph.services.local_runtime import is_ollama

        return is_ollama(self._base_url)

    async def _ollama_post(self, path: str, body: dict[str, Any], timeout: float) -> dict:
        import httpx

        from life_graph.services.local_runtime import ollama_base

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{ollama_base()}{path}", json=body)
            resp.raise_for_status()
            return resp.json()

    async def _ollama_chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: dict | None,
    ) -> str:
        from life_graph.services import local_runtime

        body: dict[str, Any] = {
            "model": model.removeprefix("ollama_chat/").removeprefix("ollama/"),
            "messages": messages,
            "stream": False,
            "keep_alive": local_runtime.keep_alive(),
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": local_runtime.num_ctx(),
            },
        }
        if settings.lm_reasoning_effort in ("none", "off", "false"):
            body["think"] = False
        if response_format:
            if response_format.get("type") == "json_schema":
                body["format"] = (response_format.get("json_schema") or {}).get("schema") or "json"
            elif response_format.get("type") == "json_object":
                body["format"] = "json"
        try:
            data = await self._ollama_post("/api/chat", body, timeout=300.0)
            return (data.get("message") or {}).get("content") or ""
        except Exception:
            logger.exception("Ollama chat request failed (model=%s)", model)
            return ""

    async def _ollama_embed(self, texts: list[str]) -> list[list[float]]:
        from life_graph.services import local_runtime

        data = await self._ollama_post(
            "/api/embed",
            {
                "model": settings.lm_embedding_model,
                "input": texts,
                "keep_alive": local_runtime.keep_alive(),
            },
            timeout=120.0,
        )
        return list(data.get("embeddings") or [])

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string (always local)."""
        if self._is_ollama:
            try:
                vectors = await self._ollama_embed([text])
                return vectors[0] if vectors else []
            except Exception:
                logger.exception("Ollama embedding failed (model=%s)", settings.lm_embedding_model)
                return []
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
        if self._is_ollama:
            try:
                vectors = await self._ollama_embed(texts)
                if len(vectors) == len(texts):
                    return vectors
                logger.warning(
                    "Ollama returned %d embeddings for %d texts", len(vectors), len(texts)
                )
            except Exception:
                logger.exception(
                    "Ollama batch embedding failed (model=%s)", settings.lm_embedding_model
                )
            return [[] for _ in texts]

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
