"""GET /jarvis/memory/overview, /memory/search and /entities/{id}
(services/jarvis_memory.py): each memory's kind, people and projects told
apart, the overview's parts failing on their own, and every query scoped to
the device's tenant. No database: sources are faked or their SQL inspected."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from life_graph.services import jarvis_memory as jm
from tests.unit.fakes import FakeResult, FakeSession, session_factory, sql

NOW = datetime(2026, 10, 25, 9, 42, tzinfo=UTC)
OVERVIEW_KEYS = {"counts", "people", "projects", "things", "rules", "recent", "days"}
COUNT_KEYS = {"total", "people", "projects", "facts", "rules", "to_review"}


def _m(content, *, props=None, tags=None, source_type="capture", status="active"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        properties=props or {},
        tags=tags,
        source_type=source_type,
        status=status,
        created_at=NOW,
    )


def _episode(day, source="jarvis"):
    label = {"jarvis": "Conversations with Jarvis", "work": "Work with the coding assistant"}
    return _m(
        f"{label[source]} on Sunday 25 October 2026: Talked about the school app.",
        props={"kind": "episode", "source": source, "date": day},
        tags=["episode", source],
        source_type="episode",
    )


def test_kind_of_each_memory():
    rule = _m("Always write local HTML files.", props={"fact_type": "explicit_save"})
    saved_rule = _m("Never use n8n.", tags=["explicit_save"], source_type="explicit")
    saved_fact = _m("My locker code is in the drawer.", source_type="explicit")
    assert jm.kind_of(rule) == "rule" and jm.kind_of(saved_rule) == "rule"
    assert jm.kind_of(saved_fact) == "fact"  # explicit, but not a rule
    # A preference saying "always" is not a rule the owner set.
    assert jm.kind_of(_m("Always tea.", props={"fact_type": "preference"})) == "preference"
    assert jm.kind_of(_m("No sugar.", props={"fact_type": "anti_preference"})) == "preference"
    assert jm.kind_of(_m("We use FastAPI.", props={"fact_type": "decision"})) == "decision"
    assert jm.kind_of(_m("Lives in Chennai.", props={"fact_type": "fact"})) == "fact"
    assert jm.kind_of(_m("Old row.", tags=["decision"])) == "decision"
    assert jm.kind_of(_episode("2026-10-24")) == "episode"
    # "never" as a whole word only.
    assert jm.kind_of(_m("Nevertheless, X.", props={"fact_type": "explicit_save"})) == "fact"


def test_rule_sql_matches_the_python_rule():
    text = sql(jm._rules_query("t-own"))
    assert "tenant_id = 't-own'" in text and "'active'" in text
    assert "'explicit_save'" in text and "~*" in text and r"\m(always|never" in text


def test_counts_query_is_this_tenants():
    text = sql(jm._counts_query("t-own"))
    assert "tenant_id = 't-own'" in text and "'pending'" in text and "'episode'" in text


def test_recent_keeps_memories_without_a_kind():
    text = sql(jm._recent_query("t-own"))
    assert "IS DISTINCT FROM" in text and "tenant_id = 't-own'" in text


def test_people_and_projects_by_contacts_and_projects():
    entities = [
        {"id": "e1", "key": "murugan", "name": "Murugan", "mentions": 9},
        {"id": "e2", "key": "life graph", "name": "Life Graph", "mentions": 7},
        {"id": "e3", "key": "priya sharma", "name": "Priya Sharma", "mentions": 3},
        {"id": "e4", "key": "tamil", "name": "Tamil", "mentions": 2},
        {"id": "e5", "key": "uzhavu race", "name": "uzhavu.race", "mentions": 2},
    ]
    people = jm.person_keys(["Murugan K", "Priya Sharma", "Al B"])
    assert "al" not in people  # first names shorter than three letters are too loose
    projects = jm.project_keys(["life-graph", "/home/raja/uzhavu.race"])
    out = jm.classify(entities, people, projects)
    assert [p["name"] for p in out["people"]] == ["Murugan", "Priya Sharma"]
    assert [p["name"] for p in out["projects"]] == ["Life Graph", "uzhavu.race"]
    assert out["things"] == [{"id": "e4", "name": "Tamil", "mentions": 2}]


def test_overview_has_every_part_of_the_contract():
    rule = _m("Always write local HTML files.", props={"fact_type": "explicit_save"})
    fact = _m("Lives in Chennai.", props={"surface": "jarvis_app"})
    src = {
        "counts": {"total": 12, "facts": 9, "rules": 1, "to_review": 4},
        "groups": {
            "people": [{"id": "e1", "name": "Murugan", "mentions": 9}],
            "projects": [{"id": "e2", "name": "Life Graph", "mentions": 7}],
            "things": [],
        },
        "rules": [rule],
        "recent": [fact, rule],
        "days": [_episode("2026-10-24"), _episode("2026-10-24", "work")],
    }
    out = jm.assemble(src)
    assert set(out) == OVERVIEW_KEYS and set(out["counts"]) == COUNT_KEYS
    assert out["counts"] == {
        "total": 12,
        "people": 1,
        "projects": 1,
        "facts": 9,
        "rules": 1,
        "to_review": 4,
    }
    assert out["rules"] == [
        {"id": str(rule.id), "content": rule.content, "created_at": NOW.isoformat()}
    ]
    assert [(r["kind"], r["source"]) for r in out["recent"]] == [
        ("fact", "Jarvis"),
        ("rule", "Life Graph"),
    ]
    assert set(out["recent"][0]) == {"id", "content", "kind", "source", "created_at"}
    assert out["days"][0] == {
        "id": str(src["days"][0].id),
        "date": "2026-10-24",
        "source": "Jarvis",
        "summary": "Talked about the school app.",
    }
    assert out["days"][1]["source"] == "Claude Code"


def test_a_failed_part_empties_only_itself():
    out = jm.assemble({"counts": {"total": 3, "facts": 3, "rules": 0, "to_review": 1}})
    assert set(out) == OVERVIEW_KEYS
    assert out["counts"]["people"] is None and out["counts"]["projects"] is None
    assert out["counts"]["total"] == 3 and out["people"] == [] and out["days"] == []
    empty = jm.assemble({})
    assert set(empty["counts"]) == COUNT_KEYS and empty["counts"]["total"] is None


@pytest.mark.asyncio
async def test_overview_survives_every_part_raising(monkeypatch, caplog):
    async def boom(*_a, **_k):
        raise RuntimeError("secret: my bank balance")

    for name in ("_counts", "_groups", "_memories"):
        monkeypatch.setattr(jm, name, boom)
    caplog.set_level("DEBUG", logger=jm.__name__)
    out = await jm.overview("t1")
    assert set(out) == OVERVIEW_KEYS and out["recent"] == []
    assert "RuntimeError" in caplog.text and "bank balance" not in caplog.text


@pytest.mark.asyncio
async def test_groups_still_come_when_contacts_fail(monkeypatch):
    async def entities(tenant_id):
        assert tenant_id == "t-own"
        return [{"id": "e1", "key": "life graph", "name": "Life Graph", "mentions": 2}]

    async def boom(tenant_id):
        raise RuntimeError("down")

    async def projects(tenant_id):
        return ["life-graph"]

    monkeypatch.setattr(jm, "_entities", entities)
    monkeypatch.setattr(jm, "_contact_names", boom)
    monkeypatch.setattr(jm, "_project_names", projects)
    out = await jm._groups("t-own")
    assert out["projects"][0]["name"] == "Life Graph" and out["people"] == []


@pytest.mark.asyncio
async def test_entity_and_name_queries_are_this_tenants(monkeypatch):
    session = FakeSession([], [], [])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    await jm._entities("t-own")
    await jm._contact_names("t-own")
    await jm._project_names("t-own")
    assert len(session.statements) == 4
    assert all("'t-own'" in sql(s) for s in session.statements)


@pytest.mark.asyncio
async def test_counts_from_one_query(monkeypatch):
    session = FakeSession(FakeResult([(12, 4, 1, 2)]))
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    assert await jm._counts("t-own") == {"total": 12, "facts": 9, "rules": 1, "to_review": 4}


@pytest.mark.asyncio
async def test_search_active_only_with_scores(monkeypatch):
    from life_graph.api import dependencies

    fact = _m("Lives in Chennai.")
    calls = {}

    class Manager:
        async def generate_embedding(self, text):
            calls["embedded"] = text
            return [0.1, 0.2]

    class Store:
        async def hybrid_search(self, **kw):
            calls.update(kw)
            return [(fact, 0.87654)]

    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: Manager())
    monkeypatch.setattr(dependencies, "get_store", lambda: Store())
    out = await jm.search("  where   do I live ", 500)
    assert calls["statuses"] == ("active",) and calls["limit"] == jm.SEARCH_MAX
    assert calls["embedded"] == "where do I live"
    assert out == [
        {
            "id": str(fact.id),
            "content": "Lives in Chennai.",
            "kind": "fact",
            "source": "Life Graph",
            "created_at": NOW.isoformat(),
            "score": 0.8765,
        }
    ]
    assert await jm.search("   ") == []


@pytest.mark.asyncio
async def test_search_without_embeddings_says_so(monkeypatch):
    from life_graph.api import dependencies

    class Manager:
        async def generate_embedding(self, text):
            return None

    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: Manager())
    with pytest.raises(jm.SearchUnavailableError):
        await jm.search("anything")


@pytest.mark.asyncio
async def test_entity_detail(monkeypatch):
    from life_graph.services import entities

    ent = SimpleNamespace(id=uuid.uuid4(), key="life graph", name="Life Graph", mentions=7)
    fact = _m("Life-Graph runs on WSL.", props={"entities": ["Life-Graph", "WSL"]})
    day = _episode("2026-10-24")
    asked = {}

    async def own(tenant_id, entity_id):
        asked["entity"] = (tenant_id, entity_id)
        return ent if entity_id == ent.id else None

    async def memories_for(tenant_id, ids, limit=20):
        asked["memories"] = (tenant_id, ids)
        return [fact, day]

    async def related(tenant_id, entity_id, memory_ids):
        asked["related"] = (tenant_id, memory_ids)
        return [{"id": "e9", "name": "WSL"}]

    monkeypatch.setattr(jm, "_entity", own)
    monkeypatch.setattr(entities, "memories_for", memories_for)
    monkeypatch.setattr(jm, "_related", related)
    out = await jm.entity_detail("t-own", ent.id)
    assert set(out) == {"id", "name", "also_called", "mentions", "memories", "related", "days"}
    assert (out["name"], out["mentions"], out["also_called"]) == ("Life Graph", 7, ["Life-Graph"])
    assert [m["id"] for m in out["memories"]] == [str(fact.id)]
    assert out["days"] == [
        {"id": str(day.id), "date": "2026-10-24", "summary": "Talked about the school app."}
    ]
    assert out["related"] == [{"id": "e9", "name": "WSL"}]
    assert asked["memories"] == ("t-own", [ent.id]) and asked["related"][0] == "t-own"
    assert await jm.entity_detail("t-own", uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_entity_detail_survives_its_memories_failing(monkeypatch):
    from life_graph.services import entities

    ent = SimpleNamespace(id=uuid.uuid4(), key="x", name="X", mentions=1)

    async def own(tenant_id, entity_id):
        return ent

    async def boom(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr(jm, "_entity", own)
    monkeypatch.setattr(entities, "memories_for", boom)
    out = await jm.entity_detail("t-own", ent.id)
    assert out["memories"] == [] and out["days"] == [] and out["related"] == []


@pytest.mark.asyncio
async def test_entity_lookup_and_related_are_this_tenants(monkeypatch):
    session = FakeSession(None, [])
    monkeypatch.setattr("life_graph.storage.database.async_session", session_factory(session))
    assert await jm._entity("t-own", uuid.uuid4()) is None
    await jm._related("t-own", uuid.uuid4(), [uuid.uuid4()])
    assert all("'t-own'" in sql(s) for s in session.statements)


@pytest.mark.asyncio
async def test_entity_endpoint_404s(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import jarvis
    from life_graph.core.tenant import tenant_scope

    async def none(tenant_id, entity_id):
        return None

    monkeypatch.setattr(jm, "entity_detail", none)
    with tenant_scope("t-own"):
        for bad in ("not-a-uuid", str(uuid.uuid4())):
            with pytest.raises(HTTPException) as err:
                await jarvis.entity(bad)
            assert err.value.status_code == 404


@pytest.mark.asyncio
async def test_search_endpoint_503_without_embeddings(monkeypatch):
    from fastapi import HTTPException

    from life_graph.api import jarvis

    async def down(q, limit=30):
        raise jm.SearchUnavailableError

    monkeypatch.setattr(jm, "search", down)
    with pytest.raises(HTTPException) as err:
        await jarvis.memory_search("x", 30)
    assert err.value.status_code == 503
