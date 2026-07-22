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


@pytest.mark.asyncio
async def test_process_voice_persists_via_manager(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "call amma tonight"}}
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]

    result = await svc.process_voice(b"RIFFfake", "note.webm", manager)

    assert result["transcript"] == "call amma tonight"
    assert result["memories_created"] == 1
    manager.ingest.assert_awaited_once_with("call amma tonight", source="voice")
    minio.upload.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_empty_transcript_raises_and_persists_nothing(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "   "}}
    manager = AsyncMock()

    with pytest.raises(ValueError):
        await svc.process_voice(b"x", "note.webm", manager)
    manager.ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_image_persists_ocr_text():
    svc, minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="Receipt total Rs 450")
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock(), MagicMock()]

    result = await svc.process_image(b"pngbytes", "receipt.png", manager)

    assert result["memories_created"] == 2
    manager.ingest.assert_awaited_once_with("Receipt total Rs 450", source="image")


@pytest.mark.asyncio
async def test_process_image_empty_ocr_raises():
    svc, _minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="")
    manager = AsyncMock()

    with pytest.raises(ValueError):
        await svc.process_image(b"pngbytes", "blank.png", manager)
    manager.ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_document_persists_each_chunk():
    svc, _minio, _bus = _service()
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]

    result = await svc.process_document(b"hello world text", "note.txt", manager)

    assert result["memories_created"] == 1
    manager.ingest.assert_awaited_once_with("hello world text", source="document")


# ── Finding 1: zero-fact extraction must not drop the raw text ──────


@pytest.mark.asyncio
async def test_process_voice_falls_back_to_raw_text_when_nothing_extracted(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "just rambling, no facts here"}}
    manager = AsyncMock()
    manager.ingest.return_value = []  # extraction pipeline found nothing

    result = await svc.process_voice(b"RIFFfake", "note.webm", manager)

    manager.ingest.assert_awaited_once_with("just rambling, no facts here", source="voice")
    manager.store.store.assert_awaited_once()
    fallback_body = manager.store.store.await_args.args[0]
    assert fallback_body.content == "just rambling, no facts here"
    assert fallback_body.source_type == "voice"
    assert result["memories_created"] >= 1


@pytest.mark.asyncio
async def test_process_image_falls_back_to_raw_text_when_nothing_extracted():
    svc, _minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="some scrawled note")
    manager = AsyncMock()
    manager.ingest.return_value = []

    result = await svc.process_image(b"pngbytes", "note.png", manager)

    manager.store.store.assert_awaited_once()
    fallback_body = manager.store.store.await_args.args[0]
    assert fallback_body.content == "some scrawled note"
    assert fallback_body.source_type == "image"
    assert result["memories_created"] >= 1


@pytest.mark.asyncio
async def test_process_document_falls_back_to_raw_text_when_nothing_extracted():
    svc, _minio, _bus = _service()
    manager = AsyncMock()
    manager.ingest.return_value = []

    result = await svc.process_document(b"hello world text", "note.txt", manager)

    manager.store.store.assert_awaited_once()
    fallback_body = manager.store.store.await_args.args[0]
    assert fallback_body.content == "hello world text"
    assert fallback_body.source_type == "document"
    assert result["memories_created"] >= 1


# ── Finding 2: local faster-whisper branch (no CF credentials) ──────


@pytest.mark.asyncio
async def test_process_voice_uses_local_whisper_when_no_cf_credentials(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "", raising=False)
    cf_spy = AsyncMock()
    monkeypatch.setattr(svc, "_transcribe_cloudflare", cf_spy)
    svc._transcribe_audio = MagicMock(return_value="local whisper transcript")
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]

    result = await svc.process_voice(b"RIFFfake", "note.wav", manager)

    cf_spy.assert_not_awaited()
    svc._transcribe_audio.assert_called_once_with(b"RIFFfake", "note.wav")
    assert result["transcript"] == "local whisper transcript"
    manager.ingest.assert_awaited_once_with("local whisper transcript", source="voice")
    minio.upload.assert_called_once()
