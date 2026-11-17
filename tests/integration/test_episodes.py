"""Conversation memory against the database (services/episodes.py).

The local model is replaced by a fake summary; everything else is real:
the day's Jarvis turns and the owner's prompts are read, one active memory per
(day, source) is written once, and a question about that day finds it.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"epi_{uuid.uuid4().hex[:8]}"
DAY = date(2026, 10, 21)


def _at(hour: int) -> datetime:
    from life_graph.connectors.tools import user_tz

    return datetime.combine(DAY, time(hour), tzinfo=user_tz()).astimezone(UTC)


async def _seed_day(tenant: str = TENANT):
    from life_graph.models.db import AgentSession, AgentTask, CaptureEvent
    from life_graph.storage.database import async_session

    async with async_session() as s:
        conv = AgentSession(tenant_id=tenant, user_message="insurance", routed_to="jarvis")
        s.add(conv)
        await s.flush()
        s.add(
            AgentTask(
                tenant_id=tenant,
                agent_name="jarvis",
                task_name="chat:jarvis",
                session_id=conv.id,
                status="completed",
                input={"message": "When does my car insurance renew?"},
                result={"response": "In March."},
                created_at=_at(10),
            )
        )
        for i, text in enumerate(
            ["Let's build the school fees module next.", "<task-notification> ignore me"]
        ):
            c = CaptureEvent(
                tenant_id=tenant,
                surface="cli",
                modality="text",
                content=text,
                content_hash=hashlib.sha256(f"{tenant}{i}".encode()).hexdigest(),
                status="processed",
                trust_tier="self",
            )
            c.created_at = c.occurred_at = _at(11 + i)
            s.add(c)
        await s.commit()


@pytest.fixture
def fakes(monkeypatch):
    from life_graph.services import episodes

    seen = []

    async def fake_summary(source, day, lines):
        seen.append((source, day, list(lines)))
        return f"FAKE {source} summary."

    class _Manager:
        async def generate_embedding(self, text):
            return None  # the test DB cannot store vectors (tests/conftest.py)

    import life_graph.api.dependencies as deps
    from life_graph.config import settings

    monkeypatch.setattr(settings, "memory_start_at", "")
    monkeypatch.setattr(episodes, "summarize", fake_summary)
    monkeypatch.setattr(deps, "get_memory_manager", lambda: _Manager())
    return seen


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_day_becomes_one_memory_per_source_once(fakes):
    from life_graph.services import episodes

    await _seed_day()
    written = await episodes.write_day(TENANT, DAY)
    assert written == [f"{DAY}:jarvis", f"{DAY}:work"]

    jarvis_lines = next(lines for src, _, lines in fakes if src == "jarvis")
    assert jarvis_lines == ["Owner: When does my car insurance renew?", "Jarvis: In March."]
    work_lines = next(lines for src, _, lines in fakes if src == "work")
    assert work_lines == ["- Let's build the school fees module next."]  # machine turn left out

    found = await episodes.episodes_between(TENANT, DAY, DAY)
    assert sorted(m.properties["source"] for m in found) == ["jarvis", "work"]
    jarvis = next(m for m in found if m.properties["source"] == "jarvis")
    assert jarvis.status == "active" and jarvis.content.startswith(
        "Conversations with Jarvis on Wednesday 21 October 2026: FAKE jarvis summary."
    )

    assert await episodes.write_day(TENANT, DAY) == []  # idempotent
    assert (
        await episodes.episodes_between(TENANT, DAY + timedelta(days=1), DAY + timedelta(days=7))
        == []
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_archived_day_is_rewritten_a_rejected_one_is_not(fakes):
    """Archived means stale, so the day is summarised again; rejected means the
    owner said no, and the day stays unwritten (2026-10-26: archived emulator
    test days came straight back)."""
    from sqlalchemy import update

    from life_graph.models.db import Memory
    from life_graph.services import episodes
    from life_graph.storage.database import async_session

    tenant = f"{TENANT}_rej"
    key = f"{DAY}:jarvis"
    await _seed_day(tenant)
    assert key in await episodes.write_day(tenant, DAY)

    async def mark(status: str):
        async with async_session() as s:
            await s.execute(
                update(Memory)
                .where(Memory.tenant_id == tenant, Memory.properties["episode_key"].astext == key)
                .values(status=status)
            )
            await s.commit()

    await mark("archived")
    assert key in await episodes.write_day(tenant, DAY)

    await mark("rejected")
    assert key not in await episodes.write_day(tenant, DAY)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_quiet_day_writes_nothing(fakes):
    from life_graph.services import episodes

    assert await episodes.write_day(f"{TENANT}_quiet", DAY) == []
    assert fakes == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_reply_asked_again_is_summarised_once(fakes):
    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.services import episodes
    from life_graph.storage.database import async_session

    tenant = f"epi_{uuid.uuid4().hex[:8]}"
    async with async_session() as s:
        conv = AgentSession(tenant_id=tenant, user_message="film", routed_to="jarvis")
        s.add(conv)
        await s.flush()
        first = AgentTask(
            tenant_id=tenant,
            agent_name="jarvis",
            task_name="chat:jarvis",
            session_id=conv.id,
            status="completed",
            input={"message": "Pick a film for tonight"},
            result={"response": "Jailer."},
            created_at=_at(20),
        )
        s.add(first)
        await s.flush()
        s.add(
            AgentTask(
                tenant_id=tenant,
                agent_name="jarvis",
                task_name="chat:jarvis",
                session_id=conv.id,
                status="completed",
                input={"message": "Pick a film for tonight", "regenerates": str(first.id)},
                result={"response": "Vikram."},
                created_at=_at(21),
            )
        )
        await s.commit()

    lines, _ = await episodes._jarvis_turns(tenant, DAY)
    assert lines == ["Owner: Pick a film for tonight", "Jarvis: Vikram."]


@pytest.mark.asyncio
@skip_on_db_error
async def test_historical_retrieve_against_postgres_respects_as_of_and_recorded_as_of(monkeypatch):
    """End-to-end DB verification for P1 Section 5:
    - Relative window ('yesterday', 'last year') anchors to as_of against real Postgres.
    - Superseded episode in Postgres is returned when recorded_as_of precedes superseded_at
      and hidden after superseded_at.
    - Late-arriving episode in Postgres is hidden when recorded_as_of precedes recorded_at
      and returned when recorded_as_of is after recorded_at.
    """
    import life_graph.runtime as runtime
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import Memory
    from life_graph.services import entities
    from life_graph.services.memory import retrieval as memory_retrieval
    from life_graph.storage.database import async_session

    tenant = f"epi_hist_{uuid.uuid4().hex[:8]}"
    as_of = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)
    june_14 = date(2025, 6, 14)
    year_2024_day = date(2024, 7, 10)

    async with async_session() as s:
        # 1. Episode on 2025-06-14 originally recorded 2025-06-15, superseded 2025-06-18
        superseded_ep = Memory(
            tenant_id=tenant,
            content="Conversations with Jarvis on Saturday 14 June 2025: First draft summary.",
            source_type="episode",
            status="superseded",
            trust_tier="verified",
            importance=0.5,
            properties={
                "kind": "episode",
                "source": "jarvis",
                "date": june_14.isoformat(),
                "episode_key": f"{june_14}:jarvis:v1",
                "recorded_at": "2025-06-15T08:00:00Z",
                "superseded_at": "2025-06-18T09:00:00Z",
            },
        )
        # 2. Late-arriving work episode for 2025-06-14 recorded on 2025-06-20
        late_ep = Memory(
            tenant_id=tenant,
            content="Work on Saturday 14 June 2025: Late backfilled work summary.",
            source_type="episode",
            status="active",
            trust_tier="verified",
            importance=0.5,
            properties={
                "kind": "episode",
                "source": "work",
                "date": june_14.isoformat(),
                "episode_key": f"{june_14}:work",
                "recorded_at": "2025-06-20T10:00:00Z",
            },
        )
        # 3. Episode from 2024 for 'last year' relative to 2025-06-15
        last_year_ep = Memory(
            tenant_id=tenant,
            content="Work on Wednesday 10 July 2024: Built the initial graph schema.",
            source_type="episode",
            status="active",
            trust_tier="verified",
            importance=0.5,
            properties={
                "kind": "episode",
                "source": "work",
                "date": year_2024_day.isoformat(),
                "episode_key": f"{year_2024_day}:work",
                "recorded_at": "2024-07-11T00:00:00Z",
            },
        )
        s.add_all([superseded_ep, late_ep, last_year_ep])
        await s.commit()

    class _Manager:
        async def generate_embedding(self, text):
            return [0.1]

    class _Store:
        async def hybrid_search(self, **kw):
            return []

    async def _no_entities(t_id, text_):
        return []

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(runtime, "get_store", lambda: _Store())
    monkeypatch.setattr(entities, "known_in_text", _no_entities)

    with tenant_scope(tenant):
        # At recorded_as_of = 2025-06-16: superseded_ep was active belief, late_ep not yet recorded
        at_june_16 = await memory_retrieval.retrieve(
            "What did we talk about yesterday?",
            as_of=as_of,
            recorded_as_of=datetime(2025, 6, 16, tzinfo=UTC),
        )
        assert [m.content for m in at_june_16] == [superseded_ep.content]

        # At recorded_as_of = 2025-06-19: superseded_ep already superseded, late_ep still not recorded
        at_june_19 = await memory_retrieval.retrieve(
            "What did we talk about yesterday?",
            as_of=as_of,
            recorded_as_of=datetime(2025, 6, 19, tzinfo=UTC),
        )
        assert at_june_19 == []

        # At recorded_as_of = 2025-06-21: late_ep is now recorded and returned
        at_june_21 = await memory_retrieval.retrieve(
            "What did we talk about yesterday?",
            as_of=as_of,
            recorded_as_of=datetime(2025, 6, 21, tzinfo=UTC),
        )
        assert [m.content for m in at_june_21] == [late_ep.content]

        # 'last year' relative to as_of=2025-06-15 retrieves the 2024 episode from Postgres
        from_2024 = await memory_retrieval.retrieve(
            "What did we work on last year?",
            as_of=as_of,
        )
        assert [m.content for m in from_2024] == [last_year_ep.content]
