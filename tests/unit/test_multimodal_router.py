"""Unit tests for the multi-modal ingest router (T-077, T-078).

Router-level tests using httpx AsyncClient + ASGITransport, per the
repo's standard pattern (see tests/integration/test_transcript.py).
No lifespan events run under ASGITransport, so no DB is required —
these tests patch the multimodal service singleton directly rather
than hitting Postgres/MinIO.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import life_graph.api.multimodal as multimodal_api
from life_graph.main import app

TENANT_HEADERS = {"X-Tenant-ID": "test-multimodal-router-tenant"}


class _RaisingService:
    """Fake MultiModalService that always raises ValueError, like an
    empty-transcript / no-text-found failure."""

    async def process_voice(self, audio_bytes, filename, tenant_id):
        raise ValueError("Transcription produced no text — nothing to remember")


class _QueuingService:
    """Fake MultiModalService that mimics the queued-ingestion response
    shape and records the tenant_id it was called with."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def process_voice(self, audio_bytes, filename, tenant_id):
        self.calls.append((audio_bytes, filename, tenant_id))
        return {"transcript": "hello", "ingest": "queued", "minio_key": "k/note.wav"}

    async def process_image(self, image_bytes, filename, tenant_id):
        self.calls.append((image_bytes, filename, tenant_id))
        return {"ocr_text": "hello", "ingest": "queued", "minio_key": "k/receipt.png"}

    async def process_document(self, doc_bytes, filename, tenant_id):
        self.calls.append((doc_bytes, filename, tenant_id))
        return {
            "text_length": 5,
            "chunks": 1,
            "ingest": "queued",
            "minio_key": "k/note.txt",
        }


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """HTTP client for multimodal router tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=TENANT_HEADERS,
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_ingest_voice_value_error_maps_to_422(client: AsyncClient, monkeypatch):
    """A ValueError raised by the service surfaces as HTTP 422, not 500."""
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: _RaisingService())

    response = await client.post(
        "/api/v1/ingest/voice",
        files={"file": ("note.wav", b"RIFFfakeaudiodata", "audio/wav")},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_voice_passes_request_tenant_id_to_service(client: AsyncClient, monkeypatch):
    """The endpoint captures tenant_id via the tenant contextvar getter
    and passes it through to the service, since the worker process has
    no request-scoped tenant context of its own."""
    fake_service = _QueuingService()
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: fake_service)

    response = await client.post(
        "/api/v1/ingest/voice",
        files={"file": ("note.wav", b"RIFFfakeaudiodata", "audio/wav")},
    )

    assert response.status_code == 200
    assert len(fake_service.calls) == 1
    _audio_bytes, _filename, tenant_id = fake_service.calls[0]
    assert tenant_id == TENANT_HEADERS["X-Tenant-ID"]
    body = response.json()
    assert body["data"]["ingest"] == "queued"


@pytest.mark.asyncio
async def test_ingest_image_passes_request_tenant_id_to_service(client: AsyncClient, monkeypatch):
    """Mirrors the voice test above for POST /ingest/image."""
    fake_service = _QueuingService()
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: fake_service)

    response = await client.post(
        "/api/v1/ingest/image",
        files={"file": ("receipt.png", b"pngbytes", "image/png")},
    )

    assert response.status_code == 200
    assert len(fake_service.calls) == 1
    _image_bytes, _filename, tenant_id = fake_service.calls[0]
    assert tenant_id == TENANT_HEADERS["X-Tenant-ID"]
    body = response.json()
    assert body["data"]["ingest"] == "queued"


@pytest.mark.asyncio
async def test_ingest_document_passes_request_tenant_id_to_service(
    client: AsyncClient, monkeypatch
):
    """Mirrors the voice test above for POST /ingest/document."""
    fake_service = _QueuingService()
    monkeypatch.setattr(multimodal_api, "_get_multimodal_service", lambda: fake_service)

    response = await client.post(
        "/api/v1/ingest/document",
        files={"file": ("note.txt", b"hello world text", "text/plain")},
    )

    assert response.status_code == 200
    assert len(fake_service.calls) == 1
    _doc_bytes, _filename, tenant_id = fake_service.calls[0]
    assert tenant_id == TENANT_HEADERS["X-Tenant-ID"]
    body = response.json()
    assert body["data"]["ingest"] == "queued"
