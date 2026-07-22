"""Unit tests for MultiModalService: transcription backend selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.config import settings
from life_graph.services.multimodal import MultiModalService


def _service() -> tuple[MultiModalService, MagicMock, AsyncMock]:
    minio = MagicMock()
    bus = AsyncMock()
    svc = MultiModalService(minio=minio, event_bus=bus, pipeline=MagicMock())
    return svc, minio, bus


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _FakeAsyncClient:
    last_request: dict | None = None
    body: dict = {"success": True, "result": {"text": "vanakkam hello"}}

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.last_request = {"url": url, "json": json, "headers": headers}
        return _FakeResponse(_FakeAsyncClient.body)


@pytest.mark.asyncio
async def test_cloudflare_backend_used_when_configured(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "vanakkam hello"}}

    transcript = await svc._transcribe_cloudflare(b"RIFFfake", "note.webm")

    assert transcript == "vanakkam hello"
    req = _FakeAsyncClient.last_request
    assert "acct123" in req["url"]
    assert "whisper-large-v3-turbo" in req["url"]
    assert req["headers"]["Authorization"] == "Bearer tok"
    assert "audio" in req["json"]  # base64 payload


@pytest.mark.asyncio
async def test_cloudflare_error_body_raises(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": False, "errors": [{"message": "boom"}]}

    with pytest.raises(RuntimeError):
        await svc._transcribe_cloudflare(b"x", "note.webm")
