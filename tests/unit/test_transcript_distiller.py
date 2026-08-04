"""Unit tests for TranscriptDistiller with all I/O mocked."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.extraction.transcript_parsers import PARSERS
from life_graph.services.transcript_distiller import (
    ExternalSessionNotFound,
    TranscriptDistiller,
)

TENANT = "test-transcript"

# Two user turns; second is new relative to last_turn_index=0 after first run.
RAW = (
    '{"type":"user","userType":"external","isSidechain":false,'
    '"timestamp":"2026-08-01T10:00:00Z","message":{"role":"user",'
    '"content":"I prefer OpenRouter free models. My key is sk-abcDEF1234567890abcdef."}}\n'
    '{"type":"user","userType":"external","isSidechain":false,'
    '"timestamp":"2026-08-01T10:05:00Z","message":{"role":"user",'
    '"content":"Deploy target is the GCP VM."}}\n'
)


def _session_obj():
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        tool="claude-code",
        external_id="sess-1",
        raw_key="staging/x.ndjson",
        line_count=2,
        last_turn_index=0,
        last_distilled_at=None,
    )


def _distiller(sess, ingest_returns):
    session = MagicMock()
    session.get = AsyncMock(return_value=sess)
    session.commit = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    manager = MagicMock()
    manager.ingest = AsyncMock(return_value=ingest_returns)
    minio = MagicMock()
    minio.download = MagicMock(return_value=RAW.encode("utf-8"))
    minio.upload = MagicMock(return_value="http://x")
    store = MagicMock()
    store.update = AsyncMock()
    # Resolve the ExternalSession by (tenant, tool, external_id) via session.get by pk;
    # the distiller looks it up by external_id, so stub the query path too.
    d = TranscriptDistiller(factory, manager, minio, store, PARSERS)
    return d, manager, minio, store, session


@pytest.mark.asyncio
async def test_distill_extracts_new_turns_and_archives(monkeypatch):
    from life_graph.core import tenant as tmod

    monkeypatch.setattr(tmod, "get_current_tenant_id", lambda: TENANT)
    from life_graph.services import transcript_distiller as td

    monkeypatch.setattr(td, "get_current_tenant_id", lambda: TENANT)

    sess = _session_obj()
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, manager, minio, store, session = _distiller(sess, [mem])
    # Make the distiller's session lookup return our session regardless of query.
    monkeypatch.setattr(d, "_load_session", AsyncMock(return_value=sess))

    result = await d.distill("sess-1")

    assert result["new_facts"] == 1
    assert result["archived"] is True
    # Extraction text must be redacted — the sk- key must not be passed to ingest.
    passed_text = (
        manager.ingest.call_args.args[0]
        if manager.ingest.call_args.args
        else manager.ingest.call_args.kwargs["text"]
    )
    assert "sk-abcDEF1234567890abcdef" not in passed_text
    # Archive uploaded to the transcripts bucket, redacted.
    assert minio.upload.call_args.args[0] == "transcripts"
    assert sess.last_turn_index == 2


@pytest.mark.asyncio
async def test_missing_session_raises(monkeypatch):
    from life_graph.services import transcript_distiller as td

    monkeypatch.setattr(td, "get_current_tenant_id", lambda: TENANT)
    d, *_ = _distiller(_session_obj(), [])
    monkeypatch.setattr(d, "_load_session", AsyncMock(return_value=None))
    with pytest.raises(ExternalSessionNotFound):
        await d.distill("nope")
