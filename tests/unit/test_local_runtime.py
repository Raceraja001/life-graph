"""Life Graph's per-request Ollama options (services/local_runtime.py) and the
native-API path of the local client (services/llm_client.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from life_graph.config import settings
from life_graph.services import local_runtime
from life_graph.services.llm_client import LMStudioClient


@pytest.fixture(autouse=True)
def _ist(monkeypatch):
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "local_llm_warm_hours", "7-23")
    monkeypatch.setattr(settings, "local_llm_idle_keep_alive", "5m")


def _ist_time(hour, minute=0):
    # Asia/Kolkata is UTC+5:30.
    total = hour * 60 + minute - 330
    return datetime(2026, 10, 22, (total // 60) % 24, total % 60, tzinfo=UTC)


def test_in_waking_hours_the_model_is_held_until_they_end():
    assert local_runtime.keep_alive(_ist_time(10)) == f"{13 * 3600}s"
    assert local_runtime.keep_alive(_ist_time(22, 58)) == "300s"  # never under 5 minutes


@pytest.mark.parametrize("hour", [23, 2, 6])
def test_at_night_it_is_released(hour):
    assert local_runtime.keep_alive(_ist_time(hour)) == "5m"


def test_a_window_across_midnight(monkeypatch):
    monkeypatch.setattr(settings, "local_llm_warm_hours", "20-2")
    assert local_runtime.keep_alive(_ist_time(23)) == f"{3 * 3600}s"
    assert local_runtime.keep_alive(_ist_time(12)) == "5m"


@pytest.mark.parametrize("spec", ["", "nonsense", "7-7"])
def test_no_or_bad_window_means_idle_keep_alive(monkeypatch, spec):
    monkeypatch.setattr(settings, "local_llm_warm_hours", spec)
    assert local_runtime.keep_alive(_ist_time(10)) == "5m"


def test_is_ollama(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_base", "http://localhost:11434")
    assert local_runtime.is_ollama("http://localhost:11434/v1")
    assert not local_runtime.is_ollama("http://localhost:1234/v1")  # LM Studio
    assert not local_runtime.is_ollama(None)


class _Recorder:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def __call__(self, path, body, timeout):
        self.calls.append((path, body))
        return self.reply


async def test_ollama_chat_sends_context_keep_alive_and_schema(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_base", "http://localhost:11434")
    monkeypatch.setattr(settings, "local_llm_num_ctx", 16384)
    monkeypatch.setattr(settings, "lm_reasoning_effort", "none")
    client = LMStudioClient(base_url="http://localhost:11434/v1")
    rec = _Recorder({"message": {"content": '{"relevant": [1]}'}})
    monkeypatch.setattr(client, "_ollama_post", rec)

    schema = {"type": "object"}
    out = await client.chat_local_only(
        [{"role": "user", "content": "q"}],
        model="qwen3:14b",
        max_tokens=50,
        response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": schema}},
    )

    assert out == '{"relevant": [1]}'
    path, body = rec.calls[0]
    assert path == "/api/chat" and body["model"] == "qwen3:14b" and body["stream"] is False
    assert body["options"]["num_ctx"] == 16384 and body["options"]["num_predict"] == 50
    assert body["keep_alive"] == local_runtime.keep_alive()
    assert body["format"] == schema and body["think"] is False


async def test_ollama_embed_batch_keeps_order_and_failures_are_empty(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_base", "http://localhost:11434")
    client = LMStudioClient(base_url="http://localhost:11434/v1")
    monkeypatch.setattr(client, "_ollama_post", _Recorder({"embeddings": [[0.1], [0.2]]}))
    assert await client.embed_batch(["a", "b"]) == [[0.1], [0.2]]
    assert await client.embed("a") == [0.1]

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(client, "_ollama_post", boom)
    assert await client.embed_batch(["a", "b"]) == [[], []]
    assert await client.chat_local_only([{"role": "user", "content": "q"}], model="m") == ""


async def test_lm_studio_keeps_the_openai_path(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_base", "http://localhost:11434")
    client = LMStudioClient(base_url="http://localhost:1234/v1")

    async def never(*a, **k):
        raise AssertionError("LM Studio must not get Ollama's native API")

    monkeypatch.setattr(client, "_ollama_post", never)

    class _Chat:
        class completions:
            @staticmethod
            async def create(**kw):
                class R:
                    choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

                return R()

    monkeypatch.setattr(client, "_get_async_client", lambda: type("A", (), {"chat": _Chat})())
    assert await client.chat_local_only([{"role": "user", "content": "q"}], model="m") == "ok"
