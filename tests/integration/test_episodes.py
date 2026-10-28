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
