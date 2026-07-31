"""Regression test for the chat-distillation idle-sweep eligibility predicate.

Final review caught a bug: ``Conversation.updated_at`` has ``onupdate=_utcnow``,
so committing ``last_distilled_at`` during a distill bumps ``updated_at`` past
the marker at flush time. A predicate comparing ``last_distilled_at`` against
``updated_at`` was therefore permanently true for any distilled conversation,
re-enqueuing it as a no-op every 15-minute sweep forever. The fix
(``life_graph.workers.distill._idle_conversations_query``) compares
``last_distilled_at`` against the newest ``ConversationMessage.created_at``
instead — real message activity, immune to the ``updated_at`` self-bump.

This test seeds rows directly (not through the API) to control
``created_at`` / ``last_distilled_at`` timestamps precisely, then runs the
exact query the worker uses (imported from ``life_graph.workers.distill``,
not duplicated) and asserts:
- a conversation just distilled (marker newer than its last message) does
  NOT qualify — the bug this test guards against;
- a conversation with a new message after its last distill DOES qualify;
- a never-distilled idle conversation DOES qualify;
- a conversation with no messages at all does NOT qualify.

Defensive per house convention: skip (not fail) when the DB is unreachable.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from life_graph.models.db import Conversation, ConversationMessage, _utcnow
from life_graph.storage.database import async_session
from life_graph.workers.distill import IDLE_MINUTES, _idle_conversations_query
from tests.integration.conftest import skip_on_db_error

# Own tenant so this test's rows can't be confused with other tests' data —
# the production query itself is intentionally global (no tenant filter),
# this is test isolation only.
TENANT = "test-distill-idle-sweep"


async def _seed_conversation(session, *, last_distilled_at, message_times) -> uuid.UUID:
    conv = Conversation(id=uuid.uuid4(), tenant_id=TENANT, last_distilled_at=last_distilled_at)
    session.add(conv)
    await session.flush()
    for t in message_times:
        session.add(
            ConversationMessage(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                tenant_id=TENANT,
                role="user",
                content="hi",
                created_at=t,
            )
        )
    await session.flush()
    return conv.id


async def _eligible_ids(session, cutoff) -> set:
    rows = await session.execute(_idle_conversations_query(cutoff))
    return {row[0] for row in rows.all() if row[1] == TENANT}


class TestIdleSweepEligibility:
    @skip_on_db_error
    async def test_just_distilled_conversation_is_excluded(self):
        """The bug: last_distilled_at newer than the last message must exclude it."""
        now = _utcnow()
        cutoff = now - timedelta(minutes=IDLE_MINUTES)
        async with async_session() as session:
            just_distilled = await _seed_conversation(
                session,
                last_distilled_at=now - timedelta(minutes=1),
                message_times=[now - timedelta(minutes=90)],
            )
            await session.commit()

            ids = await _eligible_ids(session, cutoff)

        assert just_distilled not in ids

    @skip_on_db_error
    async def test_new_message_after_distill_is_included(self):
        now = _utcnow()
        cutoff = now - timedelta(minutes=IDLE_MINUTES)
        async with async_session() as session:
            re_activated = await _seed_conversation(
                session,
                last_distilled_at=now - timedelta(minutes=60),
                message_times=[
                    now - timedelta(minutes=90),
                    now - timedelta(minutes=40),  # after last_distilled_at, and idle
                ],
            )
            await session.commit()

            ids = await _eligible_ids(session, cutoff)

        assert re_activated in ids

    @skip_on_db_error
    async def test_never_distilled_idle_conversation_is_included(self):
        now = _utcnow()
        cutoff = now - timedelta(minutes=IDLE_MINUTES)
        async with async_session() as session:
            never_distilled = await _seed_conversation(
                session,
                last_distilled_at=None,
                message_times=[now - timedelta(minutes=45)],
            )
            await session.commit()

            ids = await _eligible_ids(session, cutoff)

        assert never_distilled in ids

    @skip_on_db_error
    async def test_conversation_with_no_messages_is_excluded(self):
        now = _utcnow()
        cutoff = now - timedelta(minutes=IDLE_MINUTES)
        async with async_session() as session:
            empty = await _seed_conversation(session, last_distilled_at=None, message_times=[])
            await session.commit()

            ids = await _eligible_ids(session, cutoff)

        assert empty not in ids
