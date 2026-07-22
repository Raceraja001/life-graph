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

    async def process_voice(self, audio_bytes, filename, manager):
        raise ValueError("Transcription produced no text — nothing to remember")


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
