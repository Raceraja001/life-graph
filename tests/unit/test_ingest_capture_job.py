"""Unit tests for the ``ingest_capture_text`` ARQ job.

Covers the background half of multi-modal capture ingestion split out
of ``life_graph.services.multimodal`` (see ``docs/superpowers/sdd/task-7-*``
for the design). The job:

1. Sets the tenant contextvar (the worker process has no request-scoped
   tenant of its own).
2. Builds a ``MemoryManager`` the same way ``life_graph.api.dependencies``
   does for request handlers.
3. Runs ``ingest_or_fallback`` per chunk (one chunk for voice/image, a
   real chunking loop for documents), falling back to a raw-text store
   WITH an embedding when extraction finds zero facts — mirroring the
   fallback tests in ``test_multimodal_service.py``.
4. Emits the domain event (VOICE_TRANSCRIBED / IMAGE_PROCESSED /
   DOCUMENT_IMPORTED) exactly once, on completion, with the real memory
   count — the request-time endpoint no longer emits it.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import life_graph.workers.ingest_capture as ingest_capture_module
from life_graph.core.events import EventType
from life_graph.workers.ingest_capture import ingest_capture_text

TENANT_ID = "tenant-ingest-capture-job"


def _patch_manager(monkeypatch, manager) -> None:
    """Patch the DI provider the job imports lazily at call time."""
    import life_graph.api.dependencies as dependencies_module

    monkeypatch.setattr(dependencies_module, "get_memory_manager", lambda: manager)


def _patch_event_bus(monkeypatch) -> AsyncMock:
    """Patch the module-level event_bus singleton's emit method."""
    import life_graph.core.events as events_module

    emit_mock = AsyncMock()
    monkeypatch.setattr(events_module.event_bus, "emit", emit_mock)
    return emit_mock


@pytest.mark.asyncio
async def test_ingest_capture_text_sets_tenant_context(monkeypatch):
    set_tenant_spy = MagicMock()
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", set_tenant_spy)

    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]
    _patch_manager(monkeypatch, manager)

    await ingest_capture_text({}, "hello there", "voice", TENANT_ID)

    set_tenant_spy.assert_called_once_with(TENANT_ID, "system")


@pytest.mark.asyncio
async def test_ingest_capture_text_voice_is_a_single_chunk(monkeypatch):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock(), MagicMock()]
    _patch_manager(monkeypatch, manager)

    total = await ingest_capture_text({}, "call amma tonight", "voice", TENANT_ID)

    manager.ingest.assert_awaited_once_with("call amma tonight", source="voice")
    assert total == 2


@pytest.mark.asyncio
async def test_ingest_capture_text_image_is_a_single_chunk(monkeypatch):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]
    _patch_manager(monkeypatch, manager)

    total = await ingest_capture_text({}, "Receipt total Rs 450", "image", TENANT_ID)

    manager.ingest.assert_awaited_once_with("Receipt total Rs 450", source="image")
    assert total == 1


@pytest.mark.asyncio
async def test_ingest_capture_text_falls_back_to_raw_store_with_embedding_when_empty(
    monkeypatch,
):
    """Mirrors the fallback tests in test_multimodal_service.py: when
    ingest() extracts zero facts, the raw text is stored WITH an
    embedding rather than silently dropped."""
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = []
    manager.generate_embedding.return_value = [0.1, 0.2, 0.3]
    _patch_manager(monkeypatch, manager)

    total = await ingest_capture_text({}, "just rambling, no facts here", "voice", TENANT_ID)

    manager.generate_embedding.assert_awaited_once_with("just rambling, no facts here")
    manager.store.store.assert_awaited_once()
    fallback_body = manager.store.store.await_args.args[0]
    assert fallback_body.content == "just rambling, no facts here"
    assert fallback_body.source_type == "voice"
    assert manager.store.store.await_args.kwargs["embedding"] == [0.1, 0.2, 0.3]
    assert total == 1


@pytest.mark.asyncio
async def test_ingest_capture_text_document_loops_over_real_chunks(monkeypatch):
    """For source='document', the job splits the full text into chunks
    itself (real split_into_chunks, not mocked) and ingests each one."""
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.side_effect = lambda text, source: [MagicMock()]  # 1 memory/chunk
    _patch_manager(monkeypatch, manager)

    long_text = " ".join(f"word{i}" for i in range(1200))  # > _MAX_CHUNK_WORDS (500)

    total = await ingest_capture_text({}, long_text, "document", TENANT_ID)

    assert manager.ingest.await_count > 1  # multiple chunks were looped over
    assert total == manager.ingest.await_count
    # every call used source="document"
    for call in manager.ingest.await_args_list:
        assert call.kwargs["source"] == "document"


@pytest.mark.asyncio
async def test_ingest_capture_text_document_single_chunk_short_text(monkeypatch):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]
    _patch_manager(monkeypatch, manager)

    total = await ingest_capture_text({}, "short document text", "document", TENANT_ID)

    manager.ingest.assert_awaited_once_with("short document text", source="document")
    assert total == 1


# ── Domain-event emission (fixes the "events lost their meaning" gap:
#    the request-time endpoint used to emit these with a bogus/queued
#    payload; now the job emits once, on completion, with the real count) ──


@pytest.mark.asyncio
async def test_ingest_capture_text_emits_voice_transcribed_with_real_count_and_meta(
    monkeypatch,
):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock(), MagicMock()]  # 2 memories
    _patch_manager(monkeypatch, manager)
    emit_mock = _patch_event_bus(monkeypatch)

    total = await ingest_capture_text(
        {}, "call amma tonight", "voice", TENANT_ID,
        meta={"filename": "note.webm", "minio_key": "abc/note.webm"},
    )

    assert total == 2
    emit_mock.assert_awaited_once()
    event_type, payload = emit_mock.await_args.args
    assert event_type == EventType.VOICE_TRANSCRIBED
    assert emit_mock.await_args.kwargs["source"] == "multimodal"
    assert payload["filename"] == "note.webm"
    assert payload["minio_key"] == "abc/note.webm"
    assert payload["transcript_length"] == len("call amma tonight")
    assert payload["memories_created"] == 2


@pytest.mark.asyncio
async def test_ingest_capture_text_emits_image_processed_with_real_count_and_meta(
    monkeypatch,
):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]  # 1 memory
    _patch_manager(monkeypatch, manager)
    emit_mock = _patch_event_bus(monkeypatch)

    total = await ingest_capture_text(
        {}, "Receipt total Rs 450", "image", TENANT_ID,
        meta={"filename": "receipt.png", "minio_key": "xyz/receipt.png"},
    )

    assert total == 1
    emit_mock.assert_awaited_once()
    event_type, payload = emit_mock.await_args.args
    assert event_type == EventType.IMAGE_PROCESSED
    assert payload["filename"] == "receipt.png"
    assert payload["minio_key"] == "xyz/receipt.png"
    assert payload["ocr_text_length"] == len("Receipt total Rs 450")
    assert payload["memories_created"] == 1


@pytest.mark.asyncio
async def test_ingest_capture_text_emits_document_imported_with_chunks_and_real_count(
    monkeypatch,
):
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.side_effect = lambda text, source: [MagicMock()]  # 1 memory/chunk
    _patch_manager(monkeypatch, manager)
    emit_mock = _patch_event_bus(monkeypatch)

    long_text = " ".join(f"word{i}" for i in range(1200))  # multiple chunks

    total = await ingest_capture_text(
        {}, long_text, "document", TENANT_ID,
        meta={"filename": "big.txt", "minio_key": "doc/big.txt"},
    )

    emit_mock.assert_awaited_once()
    event_type, payload = emit_mock.await_args.args
    assert event_type == EventType.DOCUMENT_IMPORTED
    assert payload["filename"] == "big.txt"
    assert payload["minio_key"] == "doc/big.txt"
    assert payload["text_length"] == len(long_text)
    assert payload["chunks"] > 1
    assert payload["memories_created"] == total > 1


@pytest.mark.asyncio
async def test_ingest_capture_text_emits_once_even_when_nothing_extracted(monkeypatch):
    """The fallback path (raw-text store) still produces exactly one
    memory, and the event still fires once with that real count."""
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = []
    manager.generate_embedding.return_value = [0.1, 0.2, 0.3]
    _patch_manager(monkeypatch, manager)
    emit_mock = _patch_event_bus(monkeypatch)

    total = await ingest_capture_text(
        {}, "just rambling, no facts here", "voice", TENANT_ID,
        meta={"filename": "note.webm", "minio_key": "abc/note.webm"},
    )

    assert total == 1
    emit_mock.assert_awaited_once()
    _event_type, payload = emit_mock.await_args.args
    assert payload["memories_created"] == 1


@pytest.mark.asyncio
async def test_ingest_capture_text_emits_with_no_meta_defaults_to_none_fields(monkeypatch):
    """meta is optional — filename/minio_key just come through as None
    rather than raising."""
    monkeypatch.setattr(ingest_capture_module, "set_tenant_context", MagicMock())
    manager = AsyncMock()
    manager.ingest.return_value = [MagicMock()]
    _patch_manager(monkeypatch, manager)
    emit_mock = _patch_event_bus(monkeypatch)

    await ingest_capture_text({}, "hello", "voice", TENANT_ID)

    emit_mock.assert_awaited_once()
    _event_type, payload = emit_mock.await_args.args
    assert payload["filename"] is None
    assert payload["minio_key"] is None
