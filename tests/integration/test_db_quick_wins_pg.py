"""Phase-2 database fixes from the 2026-11-19 audit, against the real database.

* H7  session end and the distillers hold no transaction across the LLM call,
      and a session cannot be ended twice by two concurrent requests.
* M9  one CaptureEvent per Telegram message (migration 062's unique index).
* M19 concurrent transcript batches for one session lose no lines.
* M18 the models match the migrated schema (scripts/schema_drift.py), and the
      memory foreign keys clear instead of blocking a delete (migration 062).
* L4  ``hnsw.iterative_scan`` is accepted by the server's pgvector.
* L15 the graph pool's search_path survives the reset on release.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from tests.integration.conftest import skip_on_db_error

TENANT = f"p2db_{uuid.uuid4().hex[:8]}"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_background_consolidation(monkeypatch):
    from life_graph.api import sessions

    async def _noop(session_id):
        return None

    monkeypatch.setattr(sessions, "_run_micro_consolidation", _noop)


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": TENANT, "X-User-ID": "tester"},
    ) as c:
        yield c


async def _start(c: AsyncClient) -> str:
    r = await c.post("/api/v1/sessions/start", json={"context": {"task": "x"}})
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _idle_in_transaction_on(table: str) -> int:
    """Connections idle inside an open transaction whose last query read *table*."""
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND state = 'idle in transaction' "
                "AND query ILIKE :pat"
            ),
            {"pat": f"%{table}%"},
        )


# ── H7: session end ──────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_session_summary_is_generated_with_no_transaction_open(client, monkeypatch):
    from life_graph.api import sessions

    seen: dict[str, int] = {}

    async def _summary(sess, count):
        seen["idle_in_tx"] = await _idle_in_transaction_on("memory_sessions")
        return "A summary."

    monkeypatch.setattr(sessions, "_generate_summary", _summary)
    sid = await _start(client)

    r = await client.post(f"/api/v1/sessions/{sid}/end", json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["summary"] == "A summary."
    assert seen["idle_in_tx"] == 0, "the session row's transaction was open during the LLM call"


@pytest.mark.asyncio
@skip_on_db_error
async def test_two_concurrent_ends_give_one_200_and_one_409(client, monkeypatch):
    from life_graph.api import sessions

    both_in_llm = asyncio.Barrier(2)

    async def _summary(sess, count):
        await asyncio.wait_for(both_in_llm.wait(), timeout=10)
        return "Summary."

    monkeypatch.setattr(sessions, "_generate_summary", _summary)
    sid = await _start(client)

    r1, r2 = await asyncio.gather(
        client.post(f"/api/v1/sessions/{sid}/end", json={}),
        client.post(f"/api/v1/sessions/{sid}/end", json={}),
    )
    assert sorted([r1.status_code, r2.status_code]) == [200, 409], (r1.text, r2.text)


# ── M9: Telegram replays ─────────────────────────────────────


async def _telegram_rows(chat_id: int, message_id: int) -> list:
    from life_graph.models.db import CaptureEvent
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            text(
                "SELECT id, status FROM life_graph.capture_events "
                "WHERE tenant_id = :t AND surface = 'telegram' "
                "AND properties->>'chat_id' = :c AND properties->>'message_id' = :m"
            ),
            {"t": TENANT, "c": str(chat_id), "m": str(message_id)},
        )
        assert CaptureEvent  # imported for the model's index registration
        return list(rows.all())


async def _capture(chat_id: int, message_id: int, content: str, occurred_at=None):
    from life_graph.services.capture import CaptureService
    from life_graph.storage.database import async_session

    async with async_session() as s:
        event = await CaptureService(s).ingest(
            tenant_id=TENANT,
            surface="telegram",
            content=content,
            occurred_at=occurred_at,
            properties={"chat_id": chat_id, "message_id": message_id, "forwarded": False},
        )
        await s.commit()
        return event


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_replayed_update_twenty_minutes_later_is_one_capture():
    chat, msg = 9_000_000 + int(uuid.uuid4().int % 1000), 41
    said = datetime.now(UTC) - timedelta(minutes=25)
    first = await _capture(chat, msg, "pick up the parcel", occurred_at=said)
    # Outside the 10-minute hash window (dated on arrival), as a replay that
    # lost its message date would be.
    replay = await _capture(chat, msg, "pick up the parcel", occurred_at=None)

    assert first.status == "received"
    assert replay.status == "duplicate" and replay.id == first.id
    rows = await _telegram_rows(chat, msg)
    assert len(rows) == 1 and rows[0].status == "received", rows


@pytest.mark.asyncio
@skip_on_db_error
async def test_concurrent_deliveries_of_one_message_store_it_once():
    chat, msg = 9_100_000 + int(uuid.uuid4().int % 1000), 7
    a, b = await asyncio.gather(_capture(chat, msg, "same"), _capture(chat, msg, "same"))
    assert sorted([a.status, b.status]) == ["duplicate", "received"]
    assert len(await _telegram_rows(chat, msg)) == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_other_surfaces_and_new_messages_are_unaffected():
    chat = 9_200_000 + int(uuid.uuid4().int % 1000)
    a = await _capture(chat, 1, "first")
    b = await _capture(chat, 2, "second")
    assert a.status == b.status == "received" and a.id != b.id


# ── M19: concurrent transcript batches ───────────────────────


class _SlowMinio:
    """In-memory MinIO whose calls block like the real synchronous client."""

    objects: dict[str, bytes] = {}

    def download(self, bucket, key):
        time.sleep(0.05)
        if key not in self.objects:
            from minio.error import S3Error

            raise S3Error(None, "NoSuchKey", "missing", key, "r", "h")
        return self.objects[key]

    def upload(self, bucket, key, data, content_type=None):
        assert threading.current_thread() is not threading.main_thread()
        time.sleep(0.05)
        self.objects[key] = data
        return key


@pytest.mark.asyncio
@skip_on_db_error
async def test_concurrent_ingests_keep_every_line(monkeypatch):
    from unittest.mock import AsyncMock

    import life_graph.runtime as runtime
    from life_graph.api import transcript_ingest
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.schemas import TranscriptSessionIngest
    from life_graph.storage.database import async_session

    _SlowMinio.objects = {}
    monkeypatch.setattr(transcript_ingest, "MinIOStorage", _SlowMinio)
    monkeypatch.setattr(transcript_ingest, "get_redis", lambda: None)
    monkeypatch.setattr(runtime, "get_arq_pool", AsyncMock(return_value=AsyncMock()))

    sid = f"sess-{uuid.uuid4().hex[:8]}"

    def batch(tag: str, n: int) -> TranscriptSessionIngest:
        return TranscriptSessionIngest(
            tool="claude-code",
            session_id=sid,
            source_path="/x",
            lines=[f'{{"n":"{tag}{i}"}}' for i in range(n)],
        )

    with tenant_scope(TENANT):
        await asyncio.gather(
            *(transcript_ingest.ingest_external_transcript(batch(t, 5)) for t in "abcd")
        )

    async with async_session() as s:
        row = (
            await s.execute(
                text(
                    "SELECT line_count, raw_key FROM external_sessions "
                    "WHERE tenant_id = :t AND external_id = :e"
                ),
                {"t": TENANT, "e": sid},
            )
        ).one()
    assert row.line_count == 20, "a concurrent batch's lines were lost from the count"
    staged = _SlowMinio.objects[row.raw_key].decode().splitlines()
    assert len(staged) == 20 and len(set(staged)) == 20, "a batch's lines were overwritten"


# ── M18: foreign keys and drift ──────────────────────────────


async def _memory(**kw):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=kw.pop("content", "m"),
            tenant_id=TENANT,
            content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            status="active",
            trust_tier="self",
            source_type="test",
            properties={},
            **kw,
        )
        s.add(m)
        await s.commit()
        return m.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_deleting_a_superseded_memory_clears_the_reference():
    """Models say ON DELETE SET NULL; the database said NO ACTION until 062."""
    from life_graph.storage.database import async_session

    old = await _memory(content="lives in Madurai")
    new = await _memory(content="lives in Coimbatore", supersedes=old)
    async with async_session() as s:
        await s.execute(text("DELETE FROM memories WHERE id = :id"), {"id": old})
        await s.commit()
        assert (
            await s.scalar(text("SELECT supersedes FROM memories WHERE id = :id"), {"id": new})
        ) is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_models_match_the_migrated_schema():
    """scripts/schema_drift.py --check: no drift beyond the accepted baseline."""
    from life_graph.config import settings

    env = dict(os.environ, LIFE_GRAPH_DATABASE_URL_SYNC=settings.database_url_sync)
    out = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "scripts/schema_drift.py", "--check"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert out.returncode == 0, out.stdout + out.stderr


# ── L4 / L15 ─────────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_iterative_scan_is_accepted_by_the_server():
    import life_graph.storage.postgres as pg
    from life_graph.storage.database import async_session

    async with async_session() as s:
        version = await s.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        await pg._apply_vector_scan_settings(s, ef_search=100)
        if pg._pgvector_has_iterative_scan(version):
            assert await s.scalar(text("SHOW hnsw.iterative_scan")) == "relaxed_order"
        assert await s.scalar(text("SHOW hnsw.ef_search")) == "100"


@pytest.mark.asyncio
@skip_on_db_error
async def test_graph_search_path_survives_the_pool_reset():
    from life_graph.storage import graph as graph_module

    pool = await graph_module.GraphStore()._get_pool()
    if pool is None:
        pytest.skip("Apache AGE not available in this database")
    async with pool.acquire() as conn:
        await conn.execute("RESET ALL")  # what asyncpg does on release
        assert (await conn.fetchval("SHOW search_path")).startswith("ag_catalog")
    assert isinstance(await graph_module.GraphStore().execute_cypher("MATCH (n) RETURN n"), list)
