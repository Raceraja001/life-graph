"""Unit tests for ConversationDistiller — selection, tagging, archive, resilience."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.core import tenant as tenant_module
from life_graph.services.distillation import (
    ARCHIVE_BUCKET,
    ConversationDistiller,
    build_snapshot,
)


@pytest.fixture(autouse=True)
def _tenant():
    # Reset the tenant/user contextvars afterwards — set_tenant_context has no
    # built-in unset, and these are process-wide ContextVars, so leaving them
    # set would leak "t1" tenant context into unrelated tests run later in the
    # same session (e.g. tests asserting no-tenant-context behavior).
    tenant_token = tenant_module._tenant_id_var.set("t1")
    user_token = tenant_module._user_id_var.set("test")
    yield
    tenant_module._tenant_id_var.reset(tenant_token)
    tenant_module._user_id_var.reset(user_token)


def _msg(role, content, minutes):
    base = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        cited_memory_ids=[],
        created_at=base + timedelta(minutes=minutes),
    )


def _conv(last_distilled_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="t1",
        title="Chat",
        created_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 7, 31, 12, 30, tzinfo=UTC),
        last_distilled_at=last_distilled_at,
    )


class _FakeSession:
    """Minimal async session: returns a preset conversation + messages."""

    def __init__(self, conv, messages):
        self._conv = conv
        self._messages = messages
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, _model, _id):
        return self._conv if _id == self._conv.id else None

    async def execute(self, _query):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self._messages
        return result

    async def commit(self):
        self.committed = True


def _distiller(conv, messages, ingest_return=None, upload=None):
    session = _FakeSession(conv, messages)
    manager = SimpleNamespace(ingest=AsyncMock(return_value=ingest_return or []))
    minio = SimpleNamespace(upload=upload or MagicMock(return_value="ok"))
    store = SimpleNamespace(update=AsyncMock())
    d = ConversationDistiller(lambda: session, manager, minio, store)
    return d, session, manager, minio, store


@pytest.mark.asyncio
async def test_first_run_extracts_all_user_turns():
    conv = _conv(last_distilled_at=None)
    messages = [
        _msg("user", "insurance due Aug 20", 0),
        _msg("assistant", "Noted", 1),
        _msg("user", "and car service in Sept", 2),
    ]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, session, manager, _minio, store = _distiller(conv, messages, ingest_return=[mem])

    result = await d.distill(conv.id)

    # Only the two USER turns feed extraction, joined by newline.
    text = (
        manager.ingest.call_args.args[0]
        if manager.ingest.call_args.args
        else manager.ingest.call_args.kwargs["text"]
    )
    assert "insurance due Aug 20" in text and "car service in Sept" in text
    assert "Noted" not in text  # assistant turn excluded
    assert result["new_facts"] == 1
    assert conv.last_distilled_at is not None  # marker advanced


@pytest.mark.asyncio
async def test_incremental_only_new_turns():
    marker = datetime(2026, 7, 31, 12, 1, tzinfo=UTC)
    conv = _conv(last_distilled_at=marker)
    messages = [_msg("user", "old fact", 0), _msg("user", "new fact", 5)]  # 12:00, 12:05
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    d, *_rest = _distiller(conv, messages, ingest_return=[mem])
    manager = _rest[1]

    await d.distill(conv.id)
    text = (
        manager.ingest.call_args.args[0]
        if manager.ingest.call_args.args
        else manager.ingest.call_args.kwargs["text"]
    )
    assert "new fact" in text and "old fact" not in text  # only turns after the marker


@pytest.mark.asyncio
async def test_no_new_user_turns_is_noop_but_advances_marker():
    # Anchored to real "now" (not a hardcoded wall-clock date) so the later
    # `conv.last_distilled_at > marker` assertion — which compares against the
    # implementation's live `_utcnow()` — is deterministic regardless of when
    # the suite runs.
    marker = datetime.now(UTC) - timedelta(days=1)
    conv = _conv(last_distilled_at=marker)
    old_msg = SimpleNamespace(
        id=uuid.uuid4(),
        role="user",
        content="already distilled",
        cited_memory_ids=[],
        created_at=marker - timedelta(minutes=1),
    )
    messages = [old_msg]  # created before marker
    d, session, manager, minio, _store = _distiller(conv, messages)

    result = await d.distill(conv.id)

    manager.ingest.assert_not_called()
    assert result == {"new_facts": 0, "archived": False, "skipped": True}
    assert conv.last_distilled_at > marker  # advanced to prevent re-enqueue
    assert not (isinstance(minio.upload, MagicMock) and minio.upload.called)


@pytest.mark.asyncio
async def test_distilled_memories_tagged_and_provenanced():
    conv = _conv()
    messages = [_msg("user", "buy milk", 0)]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=["shopping"])
    d, _session, manager, _minio, store = _distiller(conv, messages, ingest_return=[mem])

    await d.distill(conv.id)

    # provenance passed to ingest as context/source
    kwargs = manager.ingest.call_args.kwargs
    assert kwargs.get("source") == "chat"
    assert kwargs.get("context", {}).get("conversation_id") == str(conv.id)
    # "chat" tag appended via store.update
    store.update.assert_awaited()
    update_arg = store.update.call_args.args[1]
    assert "chat" in update_arg.tags


@pytest.mark.asyncio
async def test_minio_failure_preserves_facts():
    conv = _conv()
    messages = [_msg("user", "fact", 0)]
    mem = SimpleNamespace(id=uuid.uuid4(), tags=[])
    boom = MagicMock(side_effect=RuntimeError("minio down"))
    d, _session, _manager, _minio, _store = _distiller(
        conv, messages, ingest_return=[mem], upload=boom
    )

    result = await d.distill(conv.id)

    assert result["new_facts"] == 1
    assert result["archived"] is False  # archive failed, facts kept, no raise


@pytest.mark.asyncio
async def test_unknown_conversation_raises():
    from life_graph.services.conversation import ConversationNotFoundError

    conv = _conv()
    d, *_ = _distiller(conv, [])
    with pytest.raises(ConversationNotFoundError):
        await d.distill(uuid.uuid4())  # different id → session.get returns None


def test_build_snapshot_shape():
    conv = _conv()
    messages = [_msg("user", "q", 0), _msg("assistant", "a", 1)]
    mids = [uuid.uuid4()]
    raw = build_snapshot(conv, messages, mids)
    doc = json.loads(raw.decode("utf-8"))
    assert doc["conversation_id"] == str(conv.id)
    assert doc["tenant_id"] == "t1"
    assert len(doc["messages"]) == 2
    assert doc["messages"][0]["role"] == "user"
    assert doc["distilled_memory_ids"] == [str(mids[0])]
    assert ARCHIVE_BUCKET == "conversations"
