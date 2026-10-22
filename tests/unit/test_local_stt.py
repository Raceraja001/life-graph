"""Local transcription through the speech server (speaches), and its guard.

The phone app's first voice question (2026-10-21) failed with a 500: the API
had no faster-whisper. Local-only voice now goes to ``stt_base_url`` when set,
and refuses a URL that is not on this machine or the private network.
"""

from __future__ import annotations

import httpx
import pytest

from life_graph.config import settings
from life_graph.services.multimodal import MultiModalService, _is_local_url


def _service() -> MultiModalService:
    return MultiModalService.__new__(MultiModalService)  # no MinIO/LLM needed


@pytest.fixture
def speaches(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), body=request.content)
        return httpx.Response(200, json={"text": " What day is it today? "})

    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(settings, "stt_base_url", "http://localhost:8010/")
    monkeypatch.setattr(settings, "stt_model", "deepdml/faster-whisper-large-v3-turbo-ct2")
    # A cloud key being set must not matter for local-only voice.
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    return seen


async def test_local_only_voice_goes_to_the_speech_server(speaches, monkeypatch):
    def no_inprocess(*a, **k):
        raise AssertionError("faster-whisper must not be loaded when stt_base_url is set")

    monkeypatch.setattr(MultiModalService, "_transcribe_audio", no_inprocess)
    text = await _service()._transcribe(b"m4a-bytes", "voice.m4a", local_only=True)
    assert text == "What day is it today?"
    assert speaches["url"] == "http://localhost:8010/v1/audio/transcriptions"
    assert b"m4a-bytes" in speaches["body"]
    assert b"faster-whisper-large-v3-turbo-ct2" in speaches["body"]


async def test_without_a_speech_server_it_falls_back_to_faster_whisper(monkeypatch):
    monkeypatch.setattr(settings, "stt_base_url", "")
    monkeypatch.setattr(MultiModalService, "_transcribe_audio", lambda self, a, f: "in process")
    assert await _service()._transcribe(b"x", "v.m4a", local_only=True) == "in process"


async def test_a_non_local_speech_server_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "stt_base_url", "https://api.example.com")
    with pytest.raises(RuntimeError, match="this machine or the private network"):
        await _service()._transcribe(b"x", "v.m4a", local_only=True)


@pytest.mark.parametrize(
    ("url", "local"),
    [
        ("http://localhost:8010", True),
        ("http://127.0.0.1:8010", True),
        ("http://192.168.1.20:8010", True),
        ("http://100.99.211.76:8010", True),  # tailnet
        ("https://race-home-pc.tailcdbd87.ts.net:8010", True),
        ("https://api.groq.com", False),
        ("http://8.8.8.8", False),
    ],
)
def test_is_local_url(url, local):
    assert _is_local_url(url) is local
