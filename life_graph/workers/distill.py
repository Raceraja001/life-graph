"""ARQ jobs for chat distillation.

``distill_conversation`` distills one conversation (mirrors the worker pattern
in ``ingest_capture``: set tenant context, build the service from DI, run it).
``distill_idle_conversations`` is the 15-minute cron sweep that enqueues every
conversation idle > IDLE_MINUTES with new activity since its last distill.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select

from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Conversation, ConversationMessage, _utcnow
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

IDLE_MINUTES = 30
MAX_ENQUEUE_PER_SWEEP = 200
DISTILL_JOB_NAME = "life_graph.workers.distill.distill_conversation"


async def distill_conversation(ctx: dict, conversation_id: str, tenant_id: str) -> dict:
    """Distill a single conversation for one tenant."""
    set_tenant_context(tenant_id, "system")

    from life_graph.api.dependencies import get_distillation_service

    distiller = get_distillation_service()
    result = await distiller.distill(uuid.UUID(conversation_id))
    logger.info("Distilled conversation %s: %s", conversation_id, result)
    return result


def _idle_conversations_query(cutoff):
    """Build the idle-sweep eligibility SELECT for a given cutoff.

    Eligibility is based on real message activity (the newest
    ``ConversationMessage.created_at`` per conversation), not
    ``Conversation.updated_at``. ``updated_at`` has ``onupdate=_utcnow``, so
    committing ``last_distilled_at`` inside ``ConversationDistiller.distill()``
    itself bumps ``updated_at`` past the marker at flush time — making
    ``last_distilled_at < updated_at`` permanently true and re-enqueuing every
    distilled conversation as a no-op forever. The latest-message time is
    immune to that self-bump: after a distill, ``last_distilled_at`` (now) is
    newer than the last message, so the conversation stops qualifying until a
    genuinely new message arrives. A conversation with no messages has
    ``last_msg IS NULL``, so ``last_msg < cutoff`` is NULL/false and it is
    correctly excluded.

    Factored out (rather than inlined in ``distill_idle_conversations``) so
    the eligibility predicate itself — the exact thing that regressed — can
    be exercised directly by tests without pulling in the enqueue/fallback
    side effects.
    """
    last_msg = (
        select(func.max(ConversationMessage.created_at))
        .where(ConversationMessage.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    return (
        select(Conversation.id, Conversation.tenant_id)
        .where(
            last_msg < cutoff,  # idle: newest message older than the cutoff
            or_(
                Conversation.last_distilled_at.is_(None),
                Conversation.last_distilled_at < last_msg,  # undistilled activity
            ),
        )
        .order_by(last_msg.asc())  # deterministic: oldest-idle first under LIMIT
        .limit(MAX_ENQUEUE_PER_SWEEP)
    )


async def distill_idle_conversations(ctx: dict) -> dict:
    """Cron: enqueue distillation for idle conversations with new activity."""
    cutoff = _utcnow() - timedelta(minutes=IDLE_MINUTES)
    async with async_session() as session:
        rows = await session.execute(_idle_conversations_query(cutoff))
        targets = list(rows.all())

    if not targets:
        return {"enqueued": 0}

    redis = ctx.get("redis")
    if redis:
        from arq import create_pool

        from life_graph.workers.settings import parse_redis_settings

        pool = await create_pool(parse_redis_settings())
        for conv_id, tenant_id in targets:
            await pool.enqueue_job(DISTILL_JOB_NAME, str(conv_id), tenant_id)
        await pool.close()
    else:  # fallback: run inline (mirrors run_all_consolidations' degraded path)
        for conv_id, tenant_id in targets:
            await distill_conversation(ctx, str(conv_id), tenant_id)

    logger.info("Enqueued distillation for %d idle conversations", len(targets))
    return {"enqueued": len(targets)}
