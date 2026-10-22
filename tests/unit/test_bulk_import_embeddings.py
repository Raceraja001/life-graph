"""Bulk import → embedding job hand-off (code review, 2026-10-22).

* ``searchable`` was ``not body.generate_embeddings`` — true exactly when no
  embeddings were requested.
* An enqueue failure was swallowed with ``pass`` and still reported success.
* ``memory.id`` was read before flush, when the column default has not fired,
  so the job was enqueued with ``None`` ids.

No database or Redis: the session and the ARQ pool are faked.
"""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace

import pytest

import life_graph.api.admin as admin
from life_graph.core.tenant import set_tenant_context


class _Session:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


_JOB = SimpleNamespace(job_id="job-1")


class _Pool:
    def __init__(self, job=_JOB, fail=False):
        self._job = job
        self._fail = fail
        self.enqueued = []
        self.closed = False

    async def enqueue_job(self, name, *args):
        if self._fail:
            raise ConnectionError("redis down")
        self.enqueued.append((name, args))
        return self._job

    async def close(self):
        self.closed = True


def _wire(monkeypatch, pool):
    import arq

    session = _Session()
    monkeypatch.setattr(admin, "async_session", lambda: session)

    async def _create_pool(*_a, **_k):
        return pool

    monkeypatch.setattr(arq, "create_pool", _create_pool)
    set_tenant_context("acme", "user-1")
    return session


def _body(n=2, generate=True):
    return admin.BulkImportRequest(
        memories=[admin.BulkImportItem(content=f"Fact {i}") for i in range(n)],
        generate_embeddings=generate,
    )


@pytest.mark.asyncio
async def test_enqueued_job_gets_the_real_row_ids_and_is_searchable(monkeypatch):
    pool = _Pool()
    session = _wire(monkeypatch, pool)

    data = (await admin.bulk_import(_body()))["data"]

    assert data == {"imported": 2, "embedding_job_id": "job-1", "searchable": True}
    ((name, (ids, tenant)),) = pool.enqueued
    assert name.endswith("generate_embeddings_batch")
    assert tenant == "acme"
    assert ids == [str(m.id) for m in session.added]
    assert all(uuid.UUID(i) for i in ids)  # not "None"
    assert pool.closed


@pytest.mark.asyncio
async def test_rows_carry_content_hash(monkeypatch):
    import hashlib

    session = _wire(monkeypatch, _Pool())

    await admin.bulk_import(_body(n=1))

    (row,) = session.added
    assert row.content_hash == hashlib.sha256(b"fact 0").hexdigest()
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_no_embeddings_requested_is_not_searchable(monkeypatch):
    pool = _Pool()
    _wire(monkeypatch, pool)

    data = (await admin.bulk_import(_body(generate=False)))["data"]

    assert data["searchable"] is False
    assert data["embedding_job_id"] is None
    assert pool.enqueued == []


@pytest.mark.asyncio
async def test_enqueue_failure_is_logged_and_not_searchable(monkeypatch, caplog):
    pool = _Pool(fail=True)
    _wire(monkeypatch, pool)

    with caplog.at_level(logging.ERROR, logger="life_graph.api.admin"):
        data = (await admin.bulk_import(_body()))["data"]

    assert data["imported"] == 2
    assert data["searchable"] is False
    assert data["embedding_job_id"] is None
    assert "failed to enqueue embedding job" in caplog.text
    assert pool.closed  # the pool is closed even when enqueue raises


@pytest.mark.asyncio
async def test_duplicate_job_none_is_not_searchable(monkeypatch, caplog):
    _wire(monkeypatch, _Pool(job=None))

    with caplog.at_level(logging.WARNING, logger="life_graph.api.admin"):
        data = (await admin.bulk_import(_body()))["data"]

    assert data["searchable"] is False
    assert "not enqueued" in caplog.text
