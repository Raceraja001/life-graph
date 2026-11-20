"""No transaction held across a model call or fetch (p2db scan, follow-ups).

Each path below read with a session, then -- with that read transaction still
open -- made a slow call (an LLM, the local model, a mail fetch), leaving the
connection "idle in transaction" for seconds to minutes:

* ConversationService.ask: retrieval + synthesis
* study.generate / study.draft (api/assistant.py, tools/assistant.py):
  write_cards_checked
* money.store (api /money/import, /money/alerts, Telegram /txn):
  categorise_with_model
* ConnectorRuntime._summarize_pending: fetch_body + summarize_email (first item)

Against the real database: inside each slow call no connection may be idle in
a transaction, and the work is still written afterwards.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text

from tests.integration.conftest import skip_on_db_error

TENANT = f"notx_{uuid.uuid4().hex[:8]}"


async def _idle_in_transaction() -> list[str]:
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    await task_events.flush()
    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT query FROM pg_stat_activity "
                    "WHERE datname = current_database() AND state = 'idle in transaction'"
                )
            )
        ).all()
        await s.rollback()
        return [r[0][:200] for r in rows]


async def _memory(content: str) -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            status="active",
            trust_tier="self",
            source_type="test",
            properties={},
        )
        s.add(m)
        await s.commit()
        return m.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_conversation_ask_holds_no_transaction_across_the_answer():
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import ConversationMessage
    from life_graph.services.conversation import ConversationService
    from life_graph.storage.database import async_session

    seen: list[list[str]] = []

    async def retrieve(question, history):
        seen.append(await _idle_in_transaction())
        return []

    async def synthesize(question, memories, history=None):
        seen.append(await _idle_in_transaction())
        return {"answer": "an answer", "citations": [], "model": "m"}

    svc = ConversationService(
        async_session, None, SimpleNamespace(synthesize=synthesize), retriever=retrieve
    )
    with tenant_scope(TENANT):
        conv = await svc.create()
        out = await svc.ask(conv.id, "what did I plan?")

    assert seen == [[], []], seen
    assert out["message"].content == "an answer"
    async with async_session() as s:
        n = await s.scalar(
            select(func.count()).where(ConversationMessage.conversation_id == conv.id)
        )
    assert n == 2


@pytest.mark.asyncio
@skip_on_db_error
async def test_study_generate_and_draft_hold_no_transaction_across_the_model(monkeypatch):
    from life_graph.services import study
    from life_graph.storage.database import async_session

    seen: list[list[str]] = []

    async def write_cards_checked(source, *, client=None):
        seen.append(await _idle_in_transaction())
        return [{"front": f"Q {uuid.uuid4().hex[:6]}", "back": "A"}], None

    monkeypatch.setattr(study, "write_cards_checked", write_cards_checked)
    topic = f"kubernetes{uuid.uuid4().hex[:6]}"
    memory_id = await _memory(f"{topic} pods restart on OOM")

    async with async_session() as s:
        out = await study.generate(s, TENANT, today=date(2026, 11, 20), topic=topic)
        await s.commit()
    assert out["added"] == 1

    async with async_session() as s:
        out = await study.draft(
            s, TENANT, today=date(2026, 11, 20), source="memory", source_id=memory_id
        )
        await s.commit()
    assert out["drafted"] == 1

    assert seen == [[], []], seen


@pytest.mark.asyncio
@skip_on_db_error
async def test_money_store_holds_no_transaction_across_the_model(monkeypatch):
    from life_graph.services.finance import money
    from life_graph.storage.database import async_session

    seen: list[list[str]] = []

    async def categorise_with_model(descriptions, client=None):
        seen.append(await _idle_in_transaction())
        return ["groceries" for _ in descriptions]

    monkeypatch.setattr(money, "categorise_with_model", categorise_with_model)
    txn = money.Txn(
        occurred_on=date(2026, 11, 20),
        amount=Decimal("123.45"),
        direction="debit",
        description=f"POS {uuid.uuid4().hex[:8]} XQZ",
    )

    async with async_session() as s:
        counts = await money.store(s, TENANT, [txn], source="alert")
        await s.commit()

    assert seen == [[]], seen
    assert counts["added"] == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_connector_summaries_hold_no_transaction_across_fetch_and_model(monkeypatch):
    from life_graph.connectors import runtime as rt
    from life_graph.connectors import store
    from life_graph.connectors import summarize as summ

    seen: list[tuple[str, list[str]]] = []
    item = SimpleNamespace(
        external_id="m1",
        title="Hello",
        sender_name="A",
        sender_addr="a@example.com",
        flags={},
        direction="received",
        occurred_at=None,
    )

    async def pending_summaries(session, row, limit):
        await session.execute(text("SELECT 1"))  # a real read: begins a transaction
        return [item]

    class _Impl:
        async def fetch_body(self, *_a):
            seen.append(("fetch", await _idle_in_transaction()))
            return "body"

    async def summarize_email(**_kw):
        seen.append(("summarize", await _idle_in_transaction()))
        return SimpleNamespace()

    applied: list[object] = []

    async def apply_summary(session, it, result):
        applied.append(it)

    monkeypatch.setattr(store, "pending_summaries", pending_summaries)
    monkeypatch.setattr(summ, "summarize_email", summarize_email)
    monkeypatch.setattr(rt, "account_view", lambda row: row)
    monkeypatch.setattr(rt.ConnectorRuntime, "_apply_summary", staticmethod(apply_summary))

    done = await rt.ConnectorRuntime(connectors={})._summarize_pending(
        SimpleNamespace(), _Impl(), {}, {}
    )

    assert done == 1 and applied == [item]
    assert seen == [("fetch", []), ("summarize", [])], seen
