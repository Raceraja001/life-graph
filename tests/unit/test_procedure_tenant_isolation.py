"""Two-tenant isolation regression tests for /procedures endpoints (P0-S1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from life_graph.api import procedures as proc_api
from life_graph.core.tenant import tenant_scope
from life_graph.models.db import Procedure
from life_graph.models.schemas import ProcedureCreate, ProcedureUpdate


class _FakeResult:
    def __init__(self, rows: list[Procedure]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Procedure]:
        return list(self._rows)


class _FakeAsyncSession:
    def __init__(self, store: dict[uuid.UUID, Procedure]) -> None:
        self._store = store

    async def __aenter__(self) -> _FakeAsyncSession:
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    def add(self, obj: Procedure) -> None:
        if obj.id is None:
            obj.id = uuid.uuid4()
        now = datetime.now(UTC)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
        if getattr(obj, "status", None) is None:
            obj.status = "active"
        if getattr(obj, "times_applied", None) is None:
            obj.times_applied = 0
        if getattr(obj, "success_count", None) is None:
            obj.success_count = 0
        if getattr(obj, "tags", None) is None:
            obj.tags = []
        if getattr(obj, "learned_from", None) is None:
            obj.learned_from = []
        self._store[obj.id] = obj

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: Procedure) -> None:
        obj.updated_at = datetime.now(UTC)

    async def get(self, model: type, pk: uuid.UUID) -> Procedure | None:
        if model is Procedure:
            return self._store.get(pk)
        return None

    async def execute(self, stmt) -> _FakeResult:
        # Evaluate the SQLAlchemy WHERE clauses against in-memory Procedure rows.
        params = stmt.compile().params
        rows = list(self._store.values())
        for key, val in params.items():
            if key.startswith("tenant_id"):
                rows = [r for r in rows if r.tenant_id == val]
            elif key.startswith("status"):
                rows = [r for r in rows if r.status == val]
            elif key.startswith("trigger"):
                needle = str(val).strip("%").lower()
                rows = [r for r in rows if needle in r.trigger.lower()]
        return _FakeResult(rows)


@pytest.fixture
def proc_store(monkeypatch):
    store: dict[uuid.UUID, Procedure] = {}
    monkeypatch.setattr(proc_api, "async_session", lambda: _FakeAsyncSession(store))
    return store


async def test_create_assigns_active_tenant_not_legacy(proc_store):
    with tenant_scope("tenant-a"):
        resp = await proc_api.create_procedure(
            ProcedureCreate(
                trigger="deploy backend",
                steps=["run tests", "restart service"],
                description="Deploy steps",
                confidence=0.8,
                tags=["ops"],
            )
        )
    proc_id = uuid.UUID(str(resp["data"].id))
    assert proc_store[proc_id].tenant_id == "tenant-a"
    assert proc_store[proc_id].tenant_id != "legacy"


async def test_cross_tenant_read_update_delete_apply_match_are_blocked(proc_store):
    with tenant_scope("tenant-a"):
        created = await proc_api.create_procedure(
            ProcedureCreate(
                trigger="secret tenant-a workflow",
                steps=["step 1"],
                confidence=0.7,
            )
        )
        proc_id = uuid.UUID(str(created["data"].id))

        # Positive: tenant-a can read, list, match, update, apply, and delete its own procedure
        got = await proc_api.get_procedure(proc_id)
        assert got["data"].id == proc_id
        listed = await proc_api.list_procedures(status_filter=None, tag=None, limit=20)
        assert [p.id for p in listed["data"]] == [proc_id]
        matched = await proc_api.match_procedures("secret", limit=5)
        assert [p.id for p in matched["data"]] == [proc_id]

    # Negative: tenant-b gets 404 (no ownership disclosure) on get/update/delete/apply,
    # and empty results on list/match.
    missing_id = uuid.uuid4()
    with tenant_scope("tenant-b"):
        with pytest.raises(HTTPException) as exc_get:
            await proc_api.get_procedure(proc_id)
        with pytest.raises(HTTPException) as exc_missing:
            await proc_api.get_procedure(missing_id)
        assert exc_get.value.status_code == 404
        assert exc_missing.value.status_code == 404
        assert exc_get.value.detail == f"Procedure {proc_id} not found"

        with pytest.raises(HTTPException) as exc_upd:
            await proc_api.update_procedure(proc_id, ProcedureUpdate(trigger="hijacked"))
        assert exc_upd.value.status_code == 404
        assert proc_store[proc_id].trigger == "secret tenant-a workflow"

        with pytest.raises(HTTPException) as exc_del:
            await proc_api.delete_procedure(proc_id)
        assert exc_del.value.status_code == 404
        assert proc_store[proc_id].status == "active"

        with pytest.raises(HTTPException) as exc_app:
            await proc_api.apply_procedure(proc_id, success=False)
        assert exc_app.value.status_code == 404
        assert proc_store[proc_id].times_applied == 0

        listed_b = await proc_api.list_procedures(status_filter=None, tag=None, limit=20)
        assert listed_b["data"] == []
        matched_b = await proc_api.match_procedures("secret", limit=5)
        assert matched_b["data"] == []

    # Positive mutation by owner tenant-a still works cleanly
    with tenant_scope("tenant-a"):
        applied = await proc_api.apply_procedure(proc_id, success=True)
        assert applied["data"].times_applied == 1
        updated = await proc_api.update_procedure(proc_id, ProcedureUpdate(description="Updated"))
        assert updated["data"].description == "Updated"
        deleted = await proc_api.delete_procedure(proc_id)
        assert deleted["data"]["status"] == "archived"
