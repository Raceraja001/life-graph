"""Unit tests for MultiModalService: transcription backend selection and
background-ingestion enqueueing.

``process_voice``/``process_image``/``process_document`` no longer call
``MemoryManager.ingest`` inline — the slow ingestion work is handed off to
the ``ingest_capture_text`` ARQ job. These tests mock the enqueue
mechanism (``life_graph.services.multimodal._enqueue_ingest_job``) and
assert the queued text/source/tenant args, instead of asserting on a
``MemoryManager`` mock.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.config import settings
from life_graph.services.multimodal import MultiModalService

TENANT_ID = "tenant-multimodal-svc"


def _service() -> tuple[MultiModalService, MagicMock, AsyncMock]:
    minio = MagicMock()
    bus = AsyncMock()
    svc = MultiModalService(minio=minio, event_bus=bus, pipeline=MagicMock())
    return svc, minio, bus


def _mock_enqueue(monkeypatch) -> AsyncMock:
    """Patch the module-level enqueue function and return the mock."""
    import life_graph.services.multimodal as multimodal_module

    mock = AsyncMock()
    monkeypatch.setattr(multimodal_module, "_enqueue_ingest_job", mock)
    return mock


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
async def test_process_voice_queues_ingestion(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "call amma tonight"}}
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.process_voice(b"RIFFfake", "note.webm", TENANT_ID)

    assert result["transcript"] == "call amma tonight"
    assert result["ingest"] == "queued"
    assert "memories_created" not in result
    enqueue.assert_awaited_once_with(
        "call amma tonight", "voice", TENANT_ID,
        meta={"filename": "note.webm", "minio_key": result["minio_key"]},
    )
    minio.upload.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_empty_transcript_raises_and_enqueues_nothing(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.body = {"success": True, "result": {"text": "   "}}
    enqueue = _mock_enqueue(monkeypatch)

    with pytest.raises(ValueError):
        await svc.process_voice(b"x", "note.webm", TENANT_ID)
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_image_queues_ocr_text(monkeypatch):
    svc, minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="Receipt total Rs 450")
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.process_image(b"pngbytes", "receipt.png", TENANT_ID)

    assert result["ingest"] == "queued"
    assert "memories_created" not in result
    enqueue.assert_awaited_once_with(
        "Receipt total Rs 450", "image", TENANT_ID,
        meta={"filename": "receipt.png", "minio_key": result["minio_key"]},
    )


@pytest.mark.asyncio
async def test_process_image_empty_ocr_raises_and_enqueues_nothing(monkeypatch):
    svc, _minio, _bus = _service()
    svc._ocr_image = MagicMock(return_value="")
    enqueue = _mock_enqueue(monkeypatch)

    with pytest.raises(ValueError):
        await svc.process_image(b"pngbytes", "blank.png", TENANT_ID)
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_document_queues_full_text_as_one_job(monkeypatch):
    svc, _minio, _bus = _service()
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.process_document(b"hello world text", "note.txt", TENANT_ID)

    assert result["ingest"] == "queued"
    assert result["chunks"] == 1
    assert "memories_created" not in result
    enqueue.assert_awaited_once_with(
        "hello world text", "document", TENANT_ID,
        meta={"filename": "note.txt", "minio_key": result["minio_key"]},
    )


@pytest.mark.asyncio
async def test_process_document_empty_text_raises_and_enqueues_nothing(monkeypatch):
    svc, _minio, _bus = _service()
    enqueue = _mock_enqueue(monkeypatch)

    with pytest.raises(ValueError):
        await svc.process_document(b"   \n\n  ", "blank.txt", TENANT_ID)
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_document_multi_chunk_still_enqueues_one_job(monkeypatch):
    """Even when the document would split into multiple chunks, exactly
    one job is enqueued with the full text — the chunking loop moved
    into the worker job."""
    svc, _minio, _bus = _service()
    enqueue = _mock_enqueue(monkeypatch)
    long_text = " ".join(f"word{i}" for i in range(1200))  # > _MAX_CHUNK_WORDS (500)

    result = await svc.process_document(long_text.encode(), "big.txt", TENANT_ID)

    assert result["chunks"] > 1  # reported count reflects multiple chunks
    enqueue.assert_awaited_once()
    args = enqueue.await_args.args
    assert args[0] == long_text  # full text, not a single chunk
    assert args[1] == "document"
    assert args[2] == TENANT_ID
    assert enqueue.await_args.kwargs["meta"] == {
        "filename": "big.txt", "minio_key": result["minio_key"],
    }


# ── Groq transcription backend (fastest, tried first) ────────────────


class _FakeGroqResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self) -> dict:
        return self._body


class _FakeGroqAsyncClient:
    last_request: dict | None = None
    response: "_FakeGroqResponse" = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, files=None, data=None):
        _FakeGroqAsyncClient.last_request = {
            "url": url,
            "headers": headers,
            "files": files,
            "data": data,
        }
        return _FakeGroqAsyncClient.response


@pytest.mark.asyncio
async def test_groq_backend_used_when_configured(monkeypatch):
    svc, minio, _bus = _service()
    # CF creds are also set — Groq must win the selection.
    monkeypatch.setattr(settings, "cf_account_id", "acct123", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "tok", raising=False)
    monkeypatch.setattr(settings, "groq_api_key", "groqkey", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeGroqAsyncClient)
    _FakeGroqAsyncClient.response = _FakeGroqResponse(200, {"text": "hello from groq"})
    cf_spy = AsyncMock()
    monkeypatch.setattr(svc, "_transcribe_cloudflare", cf_spy)
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.process_voice(b"RIFFfake", "note.webm", TENANT_ID)

    cf_spy.assert_not_awaited()
    assert result["transcript"] == "hello from groq"
    req = _FakeGroqAsyncClient.last_request
    assert req["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert req["headers"]["Authorization"] == "Bearer groqkey"
    assert "file" in req["files"]
    assert req["data"]["model"] == "whisper-large-v3-turbo"
    enqueue.assert_awaited_once_with(
        "hello from groq", "voice", TENANT_ID,
        meta={"filename": "note.webm", "minio_key": result["minio_key"]},
    )
    minio.upload.assert_called_once()


@pytest.mark.asyncio
async def test_groq_error_raises(monkeypatch):
    svc, _minio, _bus = _service()
    monkeypatch.setattr(settings, "groq_api_key", "groqkey", raising=False)
    monkeypatch.setattr("httpx.AsyncClient", _FakeGroqAsyncClient)
    _FakeGroqAsyncClient.response = _FakeGroqResponse(500, text="internal error")
    enqueue = _mock_enqueue(monkeypatch)

    with pytest.raises(RuntimeError):
        await svc.process_voice(b"RIFFfake", "note.webm", TENANT_ID)
    enqueue.assert_not_awaited()


# ── Finding 2: local faster-whisper branch (no CF credentials) ──────


@pytest.mark.asyncio
async def test_process_voice_uses_local_whisper_when_no_cf_credentials(monkeypatch):
    svc, minio, _bus = _service()
    monkeypatch.setattr(settings, "cf_account_id", "", raising=False)
    monkeypatch.setattr(settings, "cf_ai_token", "", raising=False)
    cf_spy = AsyncMock()
    monkeypatch.setattr(svc, "_transcribe_cloudflare", cf_spy)
    svc._transcribe_audio = MagicMock(return_value="local whisper transcript")
    enqueue = _mock_enqueue(monkeypatch)

    result = await svc.process_voice(b"RIFFfake", "note.wav", TENANT_ID)

    cf_spy.assert_not_awaited()
    svc._transcribe_audio.assert_called_once_with(b"RIFFfake", "note.wav")
    assert result["transcript"] == "local whisper transcript"
    enqueue.assert_awaited_once_with(
        "local whisper transcript", "voice", TENANT_ID,
        meta={"filename": "note.wav", "minio_key": result["minio_key"]},
    )
    minio.upload.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_ingest_job_passes_meta_to_pool(monkeypatch):
    """``_enqueue_ingest_job`` forwards meta (filename/minio_key) as the
    4th enqueue_job arg so the worker can rebuild the event payload."""
    import life_graph.services.multimodal as multimodal_module

    fake_pool = AsyncMock()

    async def fake_create_pool(*_args, **_kwargs):
        return fake_pool

    monkeypatch.setattr("arq.create_pool", fake_create_pool)

    await multimodal_module._enqueue_ingest_job(
        "some text", "voice", TENANT_ID, meta={"filename": "note.webm", "minio_key": "abc/note.webm"}
    )

    fake_pool.enqueue_job.assert_awaited_once_with(
        "ingest_capture_text", "some text", "voice", TENANT_ID,
        {"filename": "note.webm", "minio_key": "abc/note.webm"},
    )
    fake_pool.close.assert_awaited_once()


# ── ingest_or_fallback / split_into_chunks (module-level, shared with the
#    ingest_capture ARQ job) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_or_fallback_returns_ingest_result_when_nonempty():
    from life_graph.services.multimodal import ingest_or_fallback

    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock(), MagicMock()]

    result = await ingest_or_fallback(manager, "some text", "voice")

    assert len(result) == 2
    manager.ingest.assert_awaited_once_with("some text", source="voice")
    manager.store.store.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_or_fallback_stores_raw_text_with_embedding_when_empty():
    from life_graph.services.multimodal import ingest_or_fallback

    manager = AsyncMock()
    manager.ingest.return_value = []
    manager.generate_embedding.return_value = [0.1, 0.1, 0.1]

    result = await ingest_or_fallback(manager, "just rambling, no facts here", "voice")

    manager.generate_embedding.assert_awaited_once_with("just rambling, no facts here")
    manager.store.store.assert_awaited_once()
    fallback_body = manager.store.store.await_args.args[0]
    assert fallback_body.content == "just rambling, no facts here"
    assert fallback_body.source_type == "voice"
    assert manager.store.store.await_args.kwargs["embedding"] == [0.1, 0.1, 0.1]
    assert len(result) == 1


def test_split_into_chunks_matches_service_method():
    from life_graph.services.multimodal import split_into_chunks

    text = " ".join(f"word{i}" for i in range(1200))
    module_chunks = split_into_chunks(text)
    svc, _minio, _bus = _service()
    static_chunks = svc._split_into_chunks(text)

    assert module_chunks == static_chunks
    assert len(module_chunks) > 1
