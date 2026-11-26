"""Change detection never calls a model: not on success, not on failure.

Every way to a chat model, and the embedder, raises. The comparison, the
re-read and the baseline lookup run through success and database-failure
paths with none of them touched (Stage 1's one query embedding happens in the
snapshot, before any of this).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from life_graph import runtime
from life_graph.core.tenant import tenant_scope
from life_graph.services.llm import client as llm_client
from life_graph.services.llm import resilient
from life_graph.services.memory import changes, retrieval
from life_graph.services.memory.changes import Baseline, BaselineLookup, RowState
from life_graph.services.memory.snapshot import (
    DEFAULT_BUDGET,
    ContextItem,
    ContextSnapshot,
    SourceRef,
)

NOW = datetime.now(UTC).replace(microsecond=0)
MID = str(uuid.uuid4())


class _ForbiddenError(AssertionError):
    pass


def _boom(*a, **kw):
    raise _ForbiddenError("a model client was used by change detection")


@pytest.fixture
def no_models(monkeypatch):
    monkeypatch.setattr(llm_client.LMStudioClient, "__init__", _boom)
    monkeypatch.setattr(resilient.ResilientLLM, "__init__", _boom)
    monkeypatch.setattr(runtime, "get_lm_client", _boom)
    monkeypatch.setattr(runtime, "get_memory_manager", _boom)
    monkeypatch.setattr(retrieval, "judge", _boom)
    with tenant_scope("t-local"):
        yield


def _snap(at: datetime) -> ContextSnapshot:
    item = ContextItem(
        source_ref=SourceRef("memory", MID),
        dimension="memory",
        origin="user_stated",
        confirmed=True,
        evidence="said",
        label="owner said",
        status="active",
        reason="search_hit",
        score=0.5,
        valid_from=None,
        recorded_at=(at - timedelta(days=2)).isoformat(),
        world_time_known=False,
        freshness="fresh",
        content="x",
        fingerprint="0123456789abcdef",
    )
    return ContextSnapshot(
        query="q",
        purpose="conversation",
        as_of=None,
        reference_time=at.isoformat(),
        budget=DEFAULT_BUDGET,
        items=(item,),
        insufficient=False,
        sources=("memories",),
    )


def _lookup():
    earlier = Baseline.from_compact(_snap(NOW - timedelta(hours=2)).compact(), task_id="p")
    return BaselineLookup(earlier, frozenset())


async def test_a_comparison_with_a_change_uses_no_model(monkeypatch, no_models):
    async def baseline(task_id):
        return _lookup()

    async def resolve(refs, approvals=()):
        return {f"memory:{MID}": RowState(ref=f"memory:{MID}", missing=True)}

    monkeypatch.setattr(changes, "find_baseline", baseline)
    monkeypatch.setattr(changes, "resolve_refs", resolve)
    result = await changes.detect(_snap(NOW), uuid.uuid4(), now=NOW)
    assert [c.kind for c in result.changes] == ["deleted"]


async def test_a_failed_re_read_is_insufficient_without_any_model(monkeypatch, no_models):
    async def baseline(task_id):
        return _lookup()

    async def down(refs, approvals=()):
        raise ConnectionError("database down")

    monkeypatch.setattr(changes, "find_baseline", baseline)
    monkeypatch.setattr(changes, "resolve_refs", down)
    result = await changes.detect(_snap(NOW), uuid.uuid4(), now=NOW)
    assert result.insufficient is True and result.changes == ()


async def test_a_database_failure_in_the_real_reads_is_an_error_entry(monkeypatch, no_models):
    def no_db():
        raise ConnectionError("database down")

    monkeypatch.setattr(changes, "async_session", no_db)
    with pytest.raises(ConnectionError):
        await changes.resolve_refs([f"memory:{MID}"])
    out = await changes.shadow_changes("t-local", _snap(NOW), uuid.uuid4(), timeout=1.0)
    assert out["error"] == "ConnectionError"


async def test_no_tenant_context_raises(monkeypatch):
    def no_db():
        raise AssertionError("read before the tenant was checked")

    monkeypatch.setattr(changes, "async_session", no_db)
    with pytest.raises(RuntimeError, match="No tenant context"):
        await changes.resolve_refs([f"memory:{MID}"])
    with pytest.raises(RuntimeError, match="No tenant context"):
        await changes.find_baseline(uuid.uuid4())
