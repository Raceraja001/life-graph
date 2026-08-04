"""Unit test for the narrowed except around MinIO staging-object download in
`life_graph.api.transcript_ingest.ingest_external_transcript`.

Exercises the endpoint function directly (bypassing the ASGI app and the real
DB engine, via monkeypatched async_session/MinIOStorage) so it runs without a
live Postgres or MinIO — the integration test's valid-batch case is skipped
without a live DB, so this is the only place this specific regression
(swallowing non-"NoSuchKey" download errors and silently truncating staged
data) gets exercised in this environment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from minio.error import S3Error

from life_graph.api import transcript_ingest
from life_graph.core.tenant import set_tenant_context
from life_graph.models.schemas import TranscriptSessionIngest

PAYLOAD = TranscriptSessionIngest(
    tool="claude-code",
    session_id="sess-abc",
    source_path="~/.claude/projects/x/sess-abc.jsonl",
    lines=["line-one"],
)


def _s3_error(code: str) -> S3Error:
    return S3Error(
        response=None,
        code=code,
        message="boom",
        resource="/transcripts/staging/x",
        request_id="rid",
        host_id="hid",
    )


class _FakeSession:
    """Minimal stand-in for an AsyncSession: no existing ExternalSession row."""

    def __init__(self) -> None:
        self.add = MagicMock()
        self.commit = AsyncMock()

    async def execute(self, _stmt):
        scalars = MagicMock()
        scalars.first.return_value = None  # no existing row -> first-write path
        return SimpleNamespace(scalars=lambda: scalars)


def _fake_session_factory(session: _FakeSession):
    @asynccontextmanager
    async def factory():
        yield session

    return factory


@pytest.mark.asyncio
async def test_non_not_found_download_error_propagates_and_skips_upload(monkeypatch):
    """A transient/auth/outage error on download must NOT be treated as
    "object doesn't exist yet" — it must propagate so the request 500s and the
    uploader retries, rather than silently overwriting staged data with only
    the new batch."""
    set_tenant_context("test-tenant")

    fake_session = _FakeSession()
    monkeypatch.setattr(transcript_ingest, "async_session", _fake_session_factory(fake_session))

    fake_minio = MagicMock()
    fake_minio.download.side_effect = _s3_error("InternalError")
    monkeypatch.setattr(transcript_ingest, "MinIOStorage", lambda: fake_minio)

    with pytest.raises(S3Error) as exc_info:
        await transcript_ingest.ingest_external_transcript(PAYLOAD)

    assert exc_info.value.code == "InternalError"
    fake_minio.upload.assert_not_called()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_not_found_download_error_is_swallowed_and_upload_proceeds(monkeypatch):
    """NoSuchKey (first write for this session) must still fall back to an
    empty base and proceed — this is the one case allowed to be swallowed."""
    set_tenant_context("test-tenant")

    fake_session = _FakeSession()
    monkeypatch.setattr(transcript_ingest, "async_session", _fake_session_factory(fake_session))

    fake_minio = MagicMock()
    fake_minio.download.side_effect = _s3_error("NoSuchKey")
    monkeypatch.setattr(transcript_ingest, "MinIOStorage", lambda: fake_minio)

    # Disable the debounced-enqueue branch entirely (unrelated to this test,
    # and would otherwise try a real Redis/ARQ connection): redis.set(...)
    # returning a falsy value means "already debounced, don't enqueue".
    fake_redis = MagicMock()
    fake_redis.set = AsyncMock(return_value=False)
    monkeypatch.setattr(transcript_ingest, "get_redis", lambda: fake_redis)

    result = await transcript_ingest.ingest_external_transcript(PAYLOAD)

    assert result["data"]["session_id"] == "sess-abc"
    fake_minio.upload.assert_called_once()
    uploaded_bytes = fake_minio.upload.call_args.args[2]
    assert uploaded_bytes == b"line-one\n"
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_bucket_is_swallowed_and_upload_proceeds(monkeypatch):
    """NoSuchBucket (fresh deploy — the `transcripts` bucket doesn't exist yet)
    is also swallowed: we proceed to upload, whose ensure_bucket creates the
    bucket on the write. Without this, the very first ingest on a fresh deploy
    would 500 and never bootstrap the bucket."""
    set_tenant_context("test-tenant")

    fake_session = _FakeSession()
    monkeypatch.setattr(transcript_ingest, "async_session", _fake_session_factory(fake_session))

    fake_minio = MagicMock()
    fake_minio.download.side_effect = _s3_error("NoSuchBucket")
    monkeypatch.setattr(transcript_ingest, "MinIOStorage", lambda: fake_minio)

    fake_redis = MagicMock()
    fake_redis.set = AsyncMock(return_value=False)
    monkeypatch.setattr(transcript_ingest, "get_redis", lambda: fake_redis)

    result = await transcript_ingest.ingest_external_transcript(PAYLOAD)

    assert result["data"]["session_id"] == "sess-abc"
    fake_minio.upload.assert_called_once()
    assert fake_minio.upload.call_args.args[2] == b"line-one\n"
    fake_session.commit.assert_awaited_once()
