"""Without the minio package both routes answer 503 (audit M16 step 3)."""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile


@pytest.fixture
def no_minio(monkeypatch):
    from life_graph import runtime
    from life_graph.storage import minio_client

    def missing(*a, **k):
        raise ImportError("No module named 'minio'")

    monkeypatch.setattr(runtime, "_multimodal_service", None)
    monkeypatch.setattr(minio_client, "MinIOStorage", missing)


def test_the_runtime_names_the_missing_package(no_minio):
    from life_graph import runtime

    with pytest.raises(runtime.MultimodalUnavailableError, match="minio package"):
        runtime.get_multimodal_service()
    assert runtime._multimodal_service is None  # nothing half-built is kept


def test_the_ingest_routes_answer_503(no_minio):
    from life_graph.api import multimodal

    with pytest.raises(HTTPException) as refused:
        multimodal._get_multimodal_service()
    assert refused.value.status_code == 503
    assert refused.value.detail == "MinIO client (minio package) is not installed"


@pytest.mark.asyncio
async def test_jarvis_voice_answers_503(no_minio):
    from life_graph.api import jarvis

    audio = UploadFile(io.BytesIO(b"\x00" * 100), filename="clip.m4a")
    with pytest.raises(HTTPException) as refused:
        await jarvis._transcribe(audio)
    assert refused.value.status_code == 503
    assert refused.value.detail == "MinIO client (minio package) is not installed"
