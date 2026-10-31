"""Links between memories that strengthen with use: "fire together, wire together".

In the brain, memories formed together or recalled together become linked, and
recalling one brings up its strongest neighbours. Life Graph does the same:

- **Said together**: the facts extracted from one message are linked
  (MemoryManager.ingest / store_facts). "My wife Priya teaches at DAV; she
  takes the 8:10 bus" gives two notes that search may find one at a time.
- **Used together**: the memories one answer used are linked, or their link
  strengthened (services/memory_context.py).
- **Spreading**: the memories search finds bring their strongest active
  neighbours along as extra candidates (services/memory_retrieval.py). The
  relevance judge still decides which of them answer, so a weak link costs a
  candidate slot, never a wrong answer.

One undirected ``memory_links`` row per pair (link_type ASSOCIATED, the lower
id as source). A link fades with time unused (half-life HALF_LIFE_DAYS) and
grows with each use; it is never deleted, as no memory is.
"""

from __future__ import annotations

import itertools
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

LINK_TYPE = "ASSOCIATED"
#: Strength of a new link between facts said in one message.
SAID_TOGETHER = 0.5
#: Each use together closes this share of the gap to 1.0.
USED_TOGETHER = 0.25
#: A link unused this long counts half.
HALF_LIFE_DAYS = 180
#: Weaker links are not followed.
MIN_STRENGTH = 0.2
#: Most memories linked as one group (pairs grow with the square).
MAX_GROUP = 8

#: The link's strength now: stored strength, faded since it was last used.
_EFFECTIVE = (
    "l.strength * power(0.5, extract(epoch FROM (now() - COALESCE("
    "(l.properties->>'last_at')::timestamptz, l.created_at))) / 86400.0 / :half_life)"
)


def _pairs(ids: list[Any]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    unique = sorted({uuid.UUID(str(i)) for i in ids if i}, key=str)[:MAX_GROUP]
    return [(a, b) for a, b in itertools.combinations(unique, 2)]


async def _upsert(tenant_id: str, ids: list[Any], *, start: float, step: float, why: str) -> int:
    """New pairs start at *start*; existing ones gain *step* of the gap to 1.0."""
    pairs = _pairs(ids)
    if not pairs:
        return 0
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    now = datetime.now(UTC).isoformat()
    props = json.dumps({"why": why, "uses": 1, "last_at": now})
    sql = text(
        f"""
        INSERT INTO memory_links AS l
            (source_memory_id, target_memory_id, link_type, strength, properties, tenant_id)
        VALUES (:a, :b, '{LINK_TYPE}', :start, CAST(:props AS jsonb), :t)
        ON CONFLICT (source_memory_id, target_memory_id, link_type) DO UPDATE SET
            strength = LEAST(1.0, {_EFFECTIVE} + :step * (1.0 - {_EFFECTIVE})),
            properties = l.properties || jsonb_build_object(
                'uses', COALESCE((l.properties->>'uses')::int, 0) + 1,
                'last_at', CAST(:now AS text))
        """
    )
    async with async_session() as session:
        for a, b in pairs:
            await session.execute(
                sql,
                {
                    "a": a,
                    "b": b,
                    "start": start,
                    "step": step,
                    "props": props,
                    "now": now,
                    "t": tenant_id,
                    "half_life": HALF_LIFE_DAYS,
                },
            )
        await session.commit()
    return len(pairs)


async def said_together(tenant_id: str, ids: list[Any]) -> int:
    """Link the memories stored from one message. Best-effort: never fails the save."""
    from life_graph.config import settings

    if not settings.memory_links or len(ids) < 2:
        return 0
    try:
        return await _upsert(
            tenant_id, ids, start=SAID_TOGETHER, step=USED_TOGETHER / 2, why="said_together"
        )
    except Exception:  # noqa: BLE001 — a link is a bonus; the memories are saved
        logger.warning("Linking memories said together failed", exc_info=True)
        return 0


async def used_together(tenant_id: str, ids: list[Any]) -> int:
    """Strengthen the links between memories one answer used. Best-effort."""
    from life_graph.config import settings

    if not settings.memory_links or len(ids) < 2:
        return 0
    try:
        return await _upsert(
            tenant_id, ids, start=USED_TOGETHER, step=USED_TOGETHER, why="used_together"
        )
    except Exception:  # noqa: BLE001
        logger.warning("Strengthening links of used memories failed", exc_info=True)
        return 0


async def neighbours(tenant_id: str, ids: list[Any], limit: int = 6) -> list[Any]:
    """Active memories most strongly linked to *ids* (not *ids* themselves), strongest first.

    A seed earlier in *ids* counts more: a neighbour of the best search hit
    outranks an equally strong neighbour of the fifth.
    """
    seeds = [uuid.UUID(str(i)) for i in ids if i]
    if not seeds or limit <= 0:
        return []
    from sqlalchemy import select, text
    from sqlalchemy.orm import defer

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    weight = {s: 1.0 / (1 + n) for n, s in enumerate(seeds)}
    sql = text(
        f"""
        SELECT CASE WHEN l.source_memory_id = ANY(:seeds) THEN l.target_memory_id
                    ELSE l.source_memory_id END AS other,
               CASE WHEN l.source_memory_id = ANY(:seeds) THEN l.source_memory_id
                    ELSE l.target_memory_id END AS seed,
               {_EFFECTIVE} AS s
        FROM memory_links l
        WHERE l.tenant_id = :t AND l.link_type = '{LINK_TYPE}'
          AND (l.source_memory_id = ANY(:seeds) OR l.target_memory_id = ANY(:seeds))
        """
    )
    async with async_session() as session:
        rows = (
            await session.execute(
                sql, {"seeds": seeds, "t": tenant_id, "half_life": HALF_LIFE_DAYS}
            )
        ).all()
        score: dict[uuid.UUID, float] = {}
        for other, seed, s in rows:
            if other in weight or float(s) < MIN_STRENGTH:
                continue
            score[other] = max(score.get(other, 0.0), float(s) * weight.get(seed, 0.0))
        if not score:
            return []
        best = sorted(score, key=lambda k: -score[k])[: limit * 2]
        found = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.id.in_(best),
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                    )
                    .options(defer(Memory.embedding))
                )
            )
            .scalars()
            .all()
        )
    now = datetime.now(UTC)
    found = [m for m in found if (v := getattr(m, "valid_until", None)) is None or v > now]
    found.sort(key=lambda m: -score[m.id])
    return found[:limit]
