"""``lm_embeddings_backend``: send embeddings straight to Ollama, or not.

Prod's ``lm_studio_url`` is a llama.cpp chat server that cannot embed (501),
and turning embeddings on there would embed with the wrong model. With the
backend set to ``ollama`` the LM Studio client is never asked for an
embedding; ``auto`` keeps the old route (LM Studio first, Ollama behind it).
The fake /v1 server below counts every request the real OpenAI SDK makes.
"""

from __future__ import annotations

import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from life_graph.config import Settings, settings
from life_graph.config.llm import LLMSettings
from life_graph.services.embeddings import EmbeddingService
from life_graph.services.llm import client as client_mod
from life_graph.services.llm.client import LMStudioClient

BASE = "http://chat-only.test:11435/v1"
LM_VECTOR = [0.1, 0.2, 0.3]
OLLAMA_VECTOR = [0.9, 0.8, 0.7]


@pytest.fixture(autouse=True)
def fresh_breaker():
    client_mod._embed_skip_until.clear()
    yield
    client_mod._embed_skip_until.clear()


class Server:
    """A fake /v1 server that embeds (``ok``) or answers 501, counting calls."""

    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.mode == "501":
            return httpx.Response(
                501, json={"error": {"message": "This server does not support embeddings."}}
            )
        raw = json.loads(request.content)["input"]
        n = 1 if isinstance(raw, str) else len(raw)
        data = [{"object": "embedding", "index": i, "embedding": LM_VECTOR} for i in range(n)]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": "m",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )


def _client(server: Server, monkeypatch, backend: str):
    monkeypatch.setattr(settings, "lm_embeddings_backend", backend)
    lm = LMStudioClient(base_url=BASE, api_key="x")
    lm._async_client = AsyncOpenAI(
        base_url=BASE,
        api_key="x",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(server.handler)),
    )
    ollama_calls: list[list[str]] = []

    async def fake_ollama(texts):
        ollama_calls.append(list(texts))
        return [OLLAMA_VECTOR for _ in texts]

    monkeypatch.setattr(lm, "_ollama_embed", fake_ollama)
    return lm, ollama_calls


# ── backend = "ollama" ──────────────────────────────────────


async def test_ollama_backend_single_never_asks_lm_studio(monkeypatch):
    server = Server("ok")  # even a server that *could* embed is not asked
    lm, ollama = _client(server, monkeypatch, "ollama")
    assert await lm.embed("one") == OLLAMA_VECTOR
    assert await lm.embed("two") == OLLAMA_VECTOR
    assert server.calls == 0
    assert ollama == [["one"], ["two"]]
    assert client_mod._embed_skip_until == {}  # the breaker is not involved


async def test_ollama_backend_batch_never_asks_lm_studio(monkeypatch):
    server = Server("ok")
    lm, ollama = _client(server, monkeypatch, "ollama")
    assert await lm.embed_batch(["a", "b"]) == [OLLAMA_VECTOR, OLLAMA_VECTOR]
    assert await lm.embed_batch([]) == []
    assert server.calls == 0
    assert ollama == [["a", "b"]]


async def test_ollama_backend_failure_gives_empty_without_lm_studio(monkeypatch):
    server = Server("ok")
    lm, _ = _client(server, monkeypatch, "ollama")

    async def broken(_texts):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(lm, "_ollama_embed", broken)
    assert await lm.embed("one") == []
    assert await lm.embed_batch(["a", "b"]) == [[], []]
    assert server.calls == 0


async def test_ollama_backend_short_batch_gives_empty_per_text(monkeypatch):
    server = Server("ok")
    lm, _ = _client(server, monkeypatch, "ollama")

    async def short(_texts):
        return [OLLAMA_VECTOR]

    monkeypatch.setattr(lm, "_ollama_embed", short)
    assert await lm.embed_batch(["a", "b"]) == [[], []]
    assert server.calls == 0


async def test_ollama_backend_covers_embedding_service_and_probe(monkeypatch):
    """EmbeddingService's local mode and /health probe go through the client."""
    monkeypatch.setattr(settings, "use_local_llm", True)
    server = Server("ok")
    lm, ollama = _client(server, monkeypatch, "ollama")
    service = EmbeddingService(lm_client=lm)
    assert await service.embed_async("x") == OLLAMA_VECTOR
    assert await service.embed_batch_async(["y", "z"]) == [OLLAMA_VECTOR, OLLAMA_VECTOR]
    assert await service.probe() == "healthy"
    assert server.calls == 0
    assert ollama == [["x"], ["y", "z"], ["health"]]


# ── backend = "auto" (unchanged) ────────────────────────────


async def test_auto_backend_still_uses_lm_studio_first(monkeypatch):
    server = Server("ok")
    lm, ollama = _client(server, monkeypatch, "auto")
    assert await lm.embed("one") == LM_VECTOR
    assert await lm.embed_batch(["a", "b"]) == [LM_VECTOR, LM_VECTOR]
    assert server.calls == 2
    assert ollama == []


async def test_auto_backend_still_falls_back_and_trips_breaker(monkeypatch):
    server = Server("501")
    lm, ollama = _client(server, monkeypatch, "auto")
    assert await lm.embed("one") == OLLAMA_VECTOR
    assert await lm.embed("two") == OLLAMA_VECTOR
    assert server.calls == 1
    assert ollama == [["one"], ["two"]]
    assert BASE in client_mod._embed_skip_until


# ── the setting itself ──────────────────────────────────────


def test_default_is_auto():
    assert LLMSettings().lm_embeddings_backend == "auto"


def test_env_var_selects_ollama(monkeypatch):
    monkeypatch.setenv("LIFE_GRAPH_LM_EMBEDDINGS_BACKEND", "ollama")
    assert Settings(_env_file=None).lm_embeddings_backend == "ollama"


@pytest.mark.parametrize("value", ["lmstudio", "OLLAMA", "", "openai"])
def test_other_values_are_rejected(value):
    with pytest.raises(ValidationError):
        LLMSettings(lm_embeddings_backend=value)
