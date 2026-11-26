"""Embeddings through LM Studio: one attempt, then Ollama, and a breaker.

Prod 2026-11-26: the local /v1 server answered every embedding call with 501
"does not support embeddings"; the OpenAI SDK retried each one twice with
backoff before the Ollama fallback ran, so every embedding cost ~1.3 s.
These tests drive the real SDK client over a fake transport.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from openai import AsyncOpenAI

from life_graph.services.llm import client as client_mod
from life_graph.services.llm.client import EMBED_COOLDOWN_S, LMStudioClient

BASE = "http://lmstudio.test:1234/v1"
LM_VECTOR = [0.1, 0.2, 0.3]
OLLAMA_VECTOR = [0.9, 0.8, 0.7]


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    client_mod._embed_skip_until.clear()
    now = [1000.0]
    monkeypatch.setattr(client_mod, "_clock", lambda: now[0])
    yield now
    client_mod._embed_skip_until.clear()


class Server:
    """A fake /v1 server: counts calls and answers by *mode*."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.mode == "501":
            return httpx.Response(
                501,
                json={
                    "error": {
                        "code": 501,
                        "message": "This server does not support embeddings. "
                        "Start it with --embeddings",
                        "type": "not_supported_error",
                    }
                },
            )
        if self.mode == "500":
            return httpx.Response(500, json={"error": {"message": "boom"}})
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        raw = json.loads(request.content)["input"]
        n = 1 if isinstance(raw, str) else len(raw)
        data = [{"object": "embedding", "index": i, "embedding": LM_VECTOR} for i in range(n)]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": "bge-m3",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )


def _client(server: Server, monkeypatch) -> tuple[LMStudioClient, list[list[str]]]:
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


async def test_501_is_tried_once_then_ollama_directly(monkeypatch, caplog):
    server = Server("501")
    lm, ollama = _client(server, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=client_mod.__name__):
        assert await lm.embed("one") == OLLAMA_VECTOR
        assert server.calls == 1  # no SDK retries
        assert await lm.embed("two") == OLLAMA_VECTOR
        assert await lm.embed("three") == OLLAMA_VECTOR
    assert server.calls == 1  # breaker open: straight to Ollama
    assert ollama == [["one"], ["two"], ["three"]]
    tripped = [r for r in caplog.records if "cannot serve embeddings" in r.getMessage()]
    assert len(tripped) == 1  # logged once per trip, not per call


async def test_connection_error_is_tried_once_then_ollama_directly(monkeypatch):
    server = Server("down")
    lm, ollama = _client(server, monkeypatch)
    assert await lm.embed("one") == OLLAMA_VECTOR
    assert server.calls == 1
    assert await lm.embed("two") == OLLAMA_VECTOR
    assert server.calls == 1
    assert len(ollama) == 2


async def test_breaker_is_shared_by_clients_of_the_same_url(monkeypatch):
    server = Server("501")
    first, _ = _client(server, monkeypatch)
    second, ollama = _client(server, monkeypatch)
    await first.embed("one")
    assert await second.embed("two") == OLLAMA_VECTOR
    assert server.calls == 1
    assert ollama == [["two"]]


async def test_batch_501_is_tried_once_then_ollama_directly(monkeypatch):
    server = Server("501")
    lm, ollama = _client(server, monkeypatch)
    assert await lm.embed_batch(["a", "b"]) == [OLLAMA_VECTOR, OLLAMA_VECTOR]
    assert server.calls == 1
    assert await lm.embed_batch(["c"]) == [OLLAMA_VECTOR]
    assert await lm.embed("d") == OLLAMA_VECTOR  # one breaker for both paths
    assert server.calls == 1
    assert ollama == [["a", "b"], ["c"], ["d"]]


async def test_serving_server_is_still_used_and_ollama_never_called(monkeypatch):
    server = Server("ok")
    lm, ollama = _client(server, monkeypatch)
    assert await lm.embed("one") == LM_VECTOR
    assert await lm.embed_batch(["a", "b"]) == [LM_VECTOR, LM_VECTOR]
    assert await lm.embed("two") == LM_VECTOR
    assert server.calls == 3
    assert ollama == []
    assert client_mod._embed_skip_until == {}


async def test_other_error_falls_back_for_that_call_only(monkeypatch):
    server = Server("500")
    lm, ollama = _client(server, monkeypatch)
    assert await lm.embed("one") == OLLAMA_VECTOR
    assert server.calls == 1  # no SDK retries on a 500 either
    server.mode = "ok"
    assert await lm.embed("two") == LM_VECTOR  # not skipped: a 500 is one bad call
    assert server.calls == 2
    assert ollama == [["one"]]


async def test_cooldown_expiry_probes_again(monkeypatch, fresh_breaker, caplog):
    now = fresh_breaker
    server = Server("501")
    lm, ollama = _client(server, monkeypatch)
    await lm.embed("one")
    now[0] += EMBED_COOLDOWN_S - 1
    await lm.embed("two")
    assert server.calls == 1  # still cooling down
    now[0] += 2
    await lm.embed("three")
    assert server.calls == 2  # probed, still 501: skipped again
    await lm.embed("four")
    assert server.calls == 2
    now[0] += EMBED_COOLDOWN_S + 1
    server.mode = "ok"
    with caplog.at_level(logging.INFO, logger=client_mod.__name__):
        assert await lm.embed("five") == LM_VECTOR  # back on LM Studio
    assert server.calls == 3
    assert client_mod._embed_skip_until == {}
    assert any("serves embeddings again" in r.getMessage() for r in caplog.records)
    assert await lm.embed("six") == LM_VECTOR
    assert ollama == [["one"], ["two"], ["three"], ["four"]]


async def test_ollama_failure_with_breaker_open_gives_empty(monkeypatch):
    server = Server("501")
    lm, _ = _client(server, monkeypatch)
    await lm.embed("one")

    async def broken(_texts):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(lm, "_ollama_embed", broken)
    assert await lm.embed("two") == []
    assert await lm.embed_batch(["a", "b"]) == [[], []]
    assert server.calls == 1


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RuntimeError("This server does not support embeddings."), True),
        (RuntimeError("boom"), False),
    ],
)
def test_cannot_embed_classification(exc, expected):
    assert client_mod._cannot_embed(exc) is expected
