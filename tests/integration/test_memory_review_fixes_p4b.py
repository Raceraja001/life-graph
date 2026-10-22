"""DB-backed checks for the memory fixes from the 2026-10-22 code review.

* Bulk import: rows get real ids (the enqueued job names rows that exist)
  and a content_hash; ``searchable`` reflects whether a job was enqueued.
* Ingest: ``importance_tier`` reaches the stored row.
* Consolidation: rescoring only raises importance; duplicate pairs become
  ``kind='merge'`` approvals (idempotent, nothing deleted); distilled
  principles are stored ``pending`` through the normal store path and their
  sources are not distilled again.

Embeddings are not written here: tests/conftest.py may substitute a fake
Vector type, so the vector paths are covered by unit tests with fakes
(tests/unit/test_embedding_async_paths.py, test_reembed.py).
"""

from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from life_graph.core.tenant import set_tenant_context
from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = "test_p4b_review_tenant"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "p4b-test-user"}


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


async def _seed(content, *, importance=0.5, tier="normal", status="active", tenant=TENANT):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(content.strip().lower().encode()).hexdigest(),
            importance=importance,
            importance_tier=tier,
            status=status,
            trust_tier="verified",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m


async def _get(memory_id):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, memory_id)


def _pipeline():
    from life_graph.jobs.consolidation import ConsolidationPipeline
    from life_graph.storage.database import async_session

    embedding = MagicMock()

    async def _no_vector(_text):
        return []  # the fake Vector type cannot bind a real vector

    embedding.embed_async = _no_vector
    return ConsolidationPipeline(session_factory=async_session, embedding_service=embedding)


# ── Bulk import ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_bulk_import_enqueues_ids_of_rows_that_exist(client, monkeypatch):
    import arq

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    enqueued = []

    class _Pool:
        async def enqueue_job(self, name, ids, tenant):
            enqueued.append((ids, tenant))
            return SimpleNamespace(job_id="p4b-job")

        async def close(self):
            pass

    async def _create_pool(*_a, **_k):
        return _Pool()

    monkeypatch.setattr(arq, "create_pool", _create_pool)
    tag = f"p4b-{uuid.uuid4().hex[:8]}"

    r = await client.post(
        "/api/v1/admin/bulk/import",
        json={
            "memories": [{"content": f"P4b bulk fact {i}", "tags": [tag]} for i in range(3)],
            "generate_embeddings": True,
        },
    )

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["searchable"] is True
    assert data["embedding_job_id"] == "p4b-job"
    ((ids, tenant),) = enqueued
    assert tenant == TENANT

    async with async_session() as s:
        rows = (
            (await s.execute(select(Memory).where(Memory.id.in_([uuid.UUID(i) for i in ids]))))
            .scalars()
            .all()
        )
    assert len(rows) == 3
    assert all(row.content_hash and row.status == "pending" for row in rows)


@pytest.mark.asyncio
@skip_on_db_error
async def test_bulk_import_enqueue_failure_reports_not_searchable(client, monkeypatch):
    import arq

    async def _create_pool(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(arq, "create_pool", _create_pool)

    r = await client.post(
        "/api/v1/admin/bulk/import",
        json={"memories": [{"content": "P4b unembedded fact"}], "generate_embeddings": True},
    )

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["imported"] == 1
    assert data["searchable"] is False
    assert data["embedding_job_id"] is None


# ── Ingest: importance_tier ──────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_store_persists_importance_tier():
    from life_graph.models.schemas import MemoryCreate
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context(TENANT, "system")
    row = await PostgresMemoryStore().store(
        MemoryCreate(content=f"P4b critical constraint {uuid.uuid4()}", importance=0.95),
        status="active",
        importance_tier="critical",
    )

    assert (await _get(row.id)).importance_tier == "critical"


# ── Consolidation ────────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_rescore_never_lowers_importance():
    set_tenant_context(TENANT, "system")
    user_set = await _seed("P4b plain note", importance=0.95, tier="critical")
    low = await _seed("P4b another plain note", importance=0.1, tier="low")

    await _pipeline()._persist_scores([(user_set, 0.5, "normal"), (low, 0.75, "high")])

    kept = await _get(user_set.id)
    assert kept.importance == pytest.approx(0.95)
    assert kept.importance_tier == "critical"
    raised = await _get(low.id)
    assert raised.importance == pytest.approx(0.75)
    assert raised.importance_tier == "high"


@pytest.mark.asyncio
@skip_on_db_error
async def test_duplicates_become_merge_approvals_not_deletes():
    from life_graph.models.db import Approval
    from life_graph.services.merge_suggestions import _pair_key
    from life_graph.storage.database import async_session

    set_tenant_context(TENANT, "system")
    a = await _seed(f"P4b detailed duplicate {uuid.uuid4()}")
    b = await _seed(f"P4b dup {uuid.uuid4()}")
    pipeline = _pipeline()

    assert await pipeline._queue_merge_suggestions([(a, b, 0.97)]) == 1
    assert await pipeline._queue_merge_suggestions([(b, a, 0.97)]) == 0  # idempotent

    async with async_session() as s:
        approvals = (
            (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == TENANT,
                        Approval.source_ref == _pair_key(str(a.id), str(b.id)),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(approvals) == 1
    assert approvals[0].kind == "merge"
    assert approvals[0].status == "pending"
    # Both memories are untouched until the approval is acted on.
    assert (await _get(a.id)).status == "active"
    assert (await _get(b.id)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_distilled_principle_is_pending_and_not_redistilled(monkeypatch):
    set_tenant_context(TENANT, "system")
    sources = [await _seed(f"P4b related fact {i} {uuid.uuid4()}") for i in range(3)]
    text = f"P4b principle {uuid.uuid4()}"

    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response._hidden_params = {"response_cost": 0.0}

    async def _acompletion(**_kw):
        return response

    llm = MagicMock()
    llm.acompletion = _acompletion
    monkeypatch.setattr("life_graph.api.dependencies.get_resilient_llm", lambda: llm)

    pipeline = _pipeline()
    (principle,) = await pipeline._distill([sources])

    row = await _get(uuid.UUID(principle["id"]))
    assert row.status == "pending"
    assert row.trust_tier == "verified"
    assert row.importance_tier == "high"
    assert row.content_hash == hashlib.sha256(text.strip().lower().encode()).hexdigest()
    assert row.properties["distilled"] is True
    assert row.properties["source_memories"] == [str(m.id) for m in sources]

    # A second run over the same window must not distill the same cluster.
    assert await pipeline._distill([sources]) == []
