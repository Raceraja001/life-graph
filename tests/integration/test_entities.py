"""The entity index against the database (services/entities.py, migration 053)."""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from life_graph.core.tenant import tenant_scope
from tests.integration.conftest import skip_on_db_error

TENANT = f"ent_{uuid.uuid4().hex[:8]}"


async def _seed(content, *, status="active", tenant=TENANT):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return m


@pytest.mark.asyncio
@skip_on_db_error
async def test_names_are_normalised_linked_once_and_found_in_questions():
    from life_graph.services import entities

    a = await _seed("Murugan runs the grocery shop on Life-Graph.")
    b = await _seed("The Life Graph frontend runs on port 3006.")
    pending = await _seed("Murugan wants weekly reports.", status="pending")
    other = await _seed("Murugan of another tenant.", tenant=f"{TENANT}_x")

    assert await entities.link(TENANT, a.id, ["Murugan", "Life-Graph", "user", "app"]) == 2
    assert await entities.link(TENANT, a.id, ["murugan"]) == 0  # already linked: no double count
    assert await entities.link(TENANT, b.id, ["Life Graph", "Life Graph frontend"]) == 2
    await entities.link(TENANT, pending.id, ["Murugan"])
    await entities.link(f"{TENANT}_x", other.id, ["Murugan"])

    found = dict(
        (name, eid) for eid, name in await entities.known_in_text(TENANT, "What does MURUGAN do?")
    )
    assert list(found) == ["Murugan"]
    names = {
        n for _, n in await entities.known_in_text(TENANT, "where does the life graph frontend run")
    }
    assert names == {"Life Graph frontend", "Life-Graph"}  # both keys appear in the question

    mine = await entities.memories_for(TENANT, [found["Murugan"]])
    assert [m.id for m in mine] == [a.id]  # active only, this tenant only

    about = await entities.about(TENANT, "life graph")
    assert {m.id for m in about["memories"]} == {
        a.id,
        b.id,
    }  # "life graph" and "life graph frontend"
    assert "Murugan" in about["related"]
    # The exact name's entity, not "life graph frontend" (the phone opens it).
    ids = {n: i for i, n in await entities.known_in_text(TENANT, "the life graph frontend")}
    assert about["id"] == ids["Life-Graph"]
    assert await entities.about(TENANT, "nobody at all") is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_memory_about_tool():
    from life_graph.services import entities
    from life_graph.tools.memory_search import memory_about

    m = await _seed("Priya is the school's head teacher.")
    await entities.link(TENANT, m.id, ["Priya"])
    with tenant_scope(TENANT):
        out = json.loads(await memory_about("priya"))
        assert out["known"] and out["id"]
        assert [r["content"] for r in out["memories"]] == ["Priya is the school's head teacher."]
        assert json.loads(await memory_about("Zed"))["known"] is False
