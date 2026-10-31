"""The "What Jarvis knows about me" page against the database, through the real app.

- GET /memories/overview: review queue, the form (slotted facts by topic, with
  earlier values), notes with filters, and the cold tier without what the owner
  took back, bulk clean-ups or anything before the fresh start.
- GET /memories/{id}/connections: ASSOCIATED links, the replace chain, entities.
- Actions: correct (old superseded, approval filed, undo brings it back),
  archive / restore, drop (reject when pending, forgotten when active).
- Everything is tenant-scoped; no model is called (embeddings stubbed).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"mpage_{uuid.uuid4().hex[:8]}"
OTHER = f"other_{TENANT}"
KEY = "svc-test-key"
OWNER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": TENANT}
STRANGER = {"Authorization": f"Bearer {KEY}", "X-Tenant-ID": OTHER}


@pytest.fixture(autouse=True)
def _auth_and_no_models(monkeypatch):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.config import settings

    monkeypatch.setattr(settings, "service_api_keys", KEY)
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "memory_start_at", "")

    async def no_embedding(text):
        return None

    monkeypatch.setattr(get_memory_manager(), "generate_embedding", no_embedding)


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed(content, *, tenant=TENANT, status="active", props=None, tier="self", age_days=0):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    when = datetime.now(UTC) - timedelta(days=age_days)
    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status=status,
            trust_tier=tier,
            source_type="capture",
            properties=props or {},
            created_at=when,
            updated_at=when,
        )
        s.add(m)
        await s.commit()
        return m.id


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, mid)


async def _overview(client, **params) -> dict:
    resp = await client.get("/api/v1/memories/overview", params=params, headers=OWNER)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _ids(rows) -> set[str]:
    return {r["id"] for r in rows}


@pytest.mark.asyncio
@skip_on_db_error
async def test_overview_shows_review_form_notes_and_older(client):
    tag = uuid.uuid4().hex[:6]
    pending = await _seed(f"Owner moved to Coimbatore ({tag})", status="pending")
    job = await _seed(f"The owner works at Zoho ({tag})", props={"slot": "work.employer"})
    old_job = await _seed(
        f"The owner works at TCS ({tag})", status="superseded", props={"slot": "work.employer"}
    )
    city = await _seed(f"The owner lives in Chennai ({tag})", props={"slot": "home.city"})
    note = await _seed(f"Prefers short answers ({tag})", props={"fact_type": "preference"})
    guess = await _seed(
        f"Seems to like tea ({tag})", props={"evidence": "inferred", "fact_type": "fact"}
    )
    archived = await _seed(f"Old gym is Cult ({tag})", status="archived")
    forgotten = await _seed(f"Forgotten fact ({tag})", status="archived", props={"forgotten": {}})
    undone = await _seed(f"Undone save ({tag})", status="archived", props={"undone": {}})
    bulk = await _seed(
        f"Bulk archived ({tag})",
        status="archived",
        props={"archived_by": "fresh_start_2026-10-23"},
    )
    rejected = await _seed(f"Rejected thing ({tag})", status="rejected")
    theirs = await _seed(f"Their fact ({tag})", tenant=OTHER, props={"slot": "work.employer"})
    theirs_cold = await _seed(f"Their old fact ({tag})", tenant=OTHER, status="archived")
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        (await s.get(Memory, old_job)).superseded_by = job
        await s.commit()

    data = await _overview(client, q=tag)
    assert _ids(data["pending"]) == {str(pending)}
    topics = [g["topic"] for g in data["form"]]
    assert topics == ["home", "work"]  # slots.TOPICS order
    work = data["form"][1]["items"]
    assert [i["id"] for i in work] == [str(job)]
    assert work[0]["slot_label"] == "work · employer"
    assert [h["id"] for h in work[0]["history"]] == [str(old_job)]
    assert work[0]["history"][0]["how"] == "replaced"
    assert str(city) in _ids(data["form"][0]["items"])
    assert _ids(data["notes"]) == {str(note), str(guess)}
    cold = {r["id"]: r for r in data["cold"]}
    assert set(cold) == {str(archived), str(old_job)}
    assert cold[str(archived)]["label"] == "older note"
    assert cold[str(old_job)]["label"].startswith("later replaced on ")
    every = (
        _ids(data["pending"])
        | _ids(data["notes"])
        | set(cold)
        | {i["id"] for g in data["form"] for i in g["items"]}
    )
    for hidden in (forgotten, undone, bulk, rejected, theirs, theirs_cold):
        assert str(hidden) not in every

    # Filters: evidence and kind narrow the notes, topic the form.
    assert _ids((await _overview(client, q=tag, evidence="inferred"))["notes"]) == {str(guess)}
    assert _ids((await _overview(client, q=tag, kind="preference"))["notes"]) == {str(note)}
    assert [g["topic"] for g in (await _overview(client, q=tag, topic="work"))["form"]] == ["work"]
    bad = await client.get("/api/v1/memories/overview?evidence=rumour", headers=OWNER)
    assert bad.status_code == 422


@pytest.mark.asyncio
@skip_on_db_error
async def test_overview_leaves_out_cold_memories_before_the_fresh_start(client, monkeypatch):
    from life_graph.config import settings

    tag = uuid.uuid4().hex[:6]
    before = await _seed(f"Before the start ({tag})", status="archived", age_days=30)
    after = await _seed(f"After the start ({tag})", status="archived")
    monkeypatch.setattr(
        settings, "memory_start_at", (datetime.now(UTC) - timedelta(days=7)).isoformat()
    )
    cold = _ids((await _overview(client, q=tag))["cold"])
    assert cold == {str(after)} and str(before) not in cold


@pytest.mark.asyncio
@skip_on_db_error
async def test_connections_links_chain_and_entities(client):
    from sqlalchemy import text

    from life_graph.models.db import Memory
    from life_graph.services import entities
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    a = await _seed(f"Priya teaches at DAV ({tag})")
    b = await _seed(f"Priya takes the 8:10 bus ({tag})")
    weak = await _seed(f"Weakly linked ({tag})")
    old = await _seed(f"Priya taught at PSBB ({tag})", status="superseded")
    async with async_session() as s:
        for other, strength in ((b, 0.6), (weak, 0.3)):
            lo, hi = sorted([str(a), str(other)])
            await s.execute(
                text(
                    "INSERT INTO memory_links (id, source_memory_id, target_memory_id,"
                    " link_type, strength, properties, tenant_id)"
                    " VALUES (:id, :s, :t, 'ASSOCIATED', :st, '{}'::jsonb, :tenant)"
                ),
                {"id": uuid.uuid4(), "s": lo, "t": hi, "st": strength, "tenant": TENANT},
            )
        row = await s.get(Memory, a)
        row.supersedes = old
        await s.commit()
    await entities.link(TENANT, a, ["Priya", "DAV"])

    resp = await client.get(f"/api/v1/memories/{a}/connections", headers=OWNER)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert [m["id"] for m in data["linked"]] == [str(b), str(weak)]  # strongest first
    assert data["linked"][0]["strength"] == pytest.approx(0.6, abs=0.01)
    assert data["replaces"]["id"] == str(old)
    assert {e["name"] for e in data["entities"]} == {"Priya", "DAV"}

    other = await client.get(f"/api/v1/memories/{a}/connections", headers=STRANGER)
    assert other.status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_correct_supersedes_files_an_approval_and_undo_brings_it_back(client):
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    old = await _seed(f"The owner works at TCS ({tag})", props={"slot": "work.employer"})
    resp = await client.post(
        f"/api/v1/memories/{old}/correct",
        json={"content": f"The owner works at Zoho ({tag})"},
        headers=OWNER,
    )
    assert resp.status_code == 200, resp.text
    new_id = uuid.UUID(resp.json()["data"]["id"])
    new, was = await _row(new_id), await _row(old)
    assert (new.status, new.supersedes) == ("active", old)
    assert new.properties["slot"] == "work.employer"  # the form keeps its field
    assert new.properties["saved_by"] == "owner" and new.properties["replaces_id"] == str(old)
    assert (was.status, was.superseded_by) == ("superseded", new_id)
    async with async_session() as s:
        approval = (
            await s.execute(
                select(Approval).where(
                    Approval.tenant_id == TENANT, Approval.source_ref == f"{old}|{new_id}"
                )
            )
        ).scalar_one()
    assert approval.kind == "contradiction" and approval.payload["applied"] is True

    # The form shows the new value, with the old as "corrected" history.
    data = await _overview(client, q=tag)
    item = data["form"][0]["items"][0]
    assert item["id"] == str(new_id) and item["undoable"] is True
    assert item["history"][0]["how"] == "corrected"

    undo = await client.post(f"/api/v1/jarvis/memories/{new_id}/undo", headers=OWNER)
    assert undo.status_code == 200, undo.text
    assert (await _row(new_id)).status == "archived"
    back = await _row(old)
    assert (back.status, back.superseded_by) == ("active", None)

    # Not active any more: refused, nothing stored.
    again = await client.post(
        f"/api/v1/memories/{new_id}/correct", json={"content": "x y z"}, headers=OWNER
    )
    assert again.status_code == 409
    other = await client.post(
        f"/api/v1/memories/{old}/correct", json={"content": "Hijacked fact"}, headers=STRANGER
    )
    assert other.status_code == 404 and (await _row(old)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_archive_restore_and_drop_never_delete(client):
    tag = uuid.uuid4().hex[:6]
    note = await _seed(f"Gym is Cult ({tag})")
    pending = await _seed(f"Maybe moved ({tag})", status="pending")
    replaced = await _seed(f"Old value ({tag})", status="superseded")

    ok = await client.post(f"/api/v1/memories/{note}/archive", headers=OWNER)
    assert ok.status_code == 200 and (await _row(note)).properties["archived_by"] == "owner"
    assert str(note) in _ids((await _overview(client, q=tag))["cold"])  # shown as older
    assert (await client.post(f"/api/v1/memories/{note}/archive", headers=OWNER)).status_code == 409

    back = await client.post(f"/api/v1/memories/{note}/restore", headers=OWNER)
    assert back.status_code == 200 and (await _row(note)).status == "active"
    # A replaced memory is history: bring back refuses it.
    no = await client.post(f"/api/v1/memories/{replaced}/restore", headers=OWNER)
    assert no.status_code == 409 and (await _row(replaced)).status == "superseded"

    # Drop an active memory: taken back, hidden from the cold tier; restore undoes it.
    dropped = await client.post(f"/api/v1/memories/{note}/drop", headers=OWNER)
    assert dropped.status_code == 200 and dropped.json()["data"]["forgotten"] is True
    row = await _row(note)
    assert row.status == "archived" and row.properties["forgotten"]["by"] == "owner"
    assert str(note) not in _ids((await _overview(client, q=tag))["cold"])
    assert (await client.post(f"/api/v1/memories/{note}/restore", headers=OWNER)).status_code == 200
    row = await _row(note)
    assert row.status == "active" and "forgotten" not in row.properties

    # Drop a pending one: the review queue's reject.
    rej = await client.post(f"/api/v1/memories/{pending}/drop", headers=OWNER)
    assert rej.status_code == 200 and (await _row(pending)).status == "rejected"

    # Another tenant's id: not found, untouched.
    for action in ("archive", "drop", "restore"):
        resp = await client.post(f"/api/v1/memories/{note}/{action}", headers=STRANGER)
        assert resp.status_code == 404
    assert (await _row(note)).status == "active"
