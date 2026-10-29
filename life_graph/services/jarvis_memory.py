"""The phone's Memory screens (life-graph-android docs/PLAN-v4.md, S2).

``GET /jarvis/memory/overview``, ``.../memory/search`` and
``/jarvis/entities/{id}`` (api/jarvis.py) read the owner's active memories,
the entity index (services/entities.py) and the daily episodes
(services/episodes.py). The overview reads each part on its own, as the
Today screen does: a part that fails is null or empty, never a 500, logged
at debug level by part name and exception type only.

A memory's ``kind``:

* ``episode``: a day's summary (``properties.kind = "episode"``);
* ``rule``: a standing instruction. Nothing stores "this is a rule": a rule
  the owner set is kept as an ``explicit_save`` fact
  (capture_processors.promote_standing, or Jarvis's memory_save), so a rule
  is an explicit save that says always / never / from now on / every time /
  each time (the words promote_standing looks for);
* ``preference`` / ``decision``: the extractor's ``fact_type`` (an
  anti-preference is a preference);
* ``fact``: everything else.

Entities carry no type either. People are the entities named like one of the
owner's contacts (full name, or first name of three letters or more);
projects are the entities named like a registered project or the project a
capture came from. The rest are ``things``: the contract has no list for
them, so the overview adds one.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable, Iterable

logger = logging.getLogger(__name__)

#: The words that make an explicit save a rule (capture_processors._STANDING).
RULE_WORDS = ("always", "never", "from now on", "every time", "each time")
_RULE = re.compile(r"\b(" + "|".join(RULE_WORDS) + r")\b", re.IGNORECASE)
_RULE_SQL = r"\m(" + "|".join(RULE_WORDS) + r")\M"
_PREFERENCE_TYPES = frozenset({"preference", "anti_preference"})
EPISODE = "episode"
MAX_LIST = 20
MAX_DAYS = 14
MAX_ENTITIES = 1000
MAX_ENTITY_MEMORIES = 60
MAX_RELATED = 8
MIN_FIRST_NAME = 3
SEARCH_DEFAULT = 30
SEARCH_MAX = 100
#: Who a day's summary is of (services/episodes.py SOURCES), in the app's words.
_DAY_SOURCE = {"jarvis": "Jarvis", "work": "Claude Code"}


async def _read(name: str, fn: Callable[[], Awaitable[Any]]) -> Any:
    """``await fn()``, or None when it fails: one broken part never fails the screen."""
    try:
        return await fn()
    except Exception as exc:  # noqa: BLE001 - every failure is this part's null
        logger.debug("memory: %s unavailable (%s)", name, type(exc).__name__)
        return None


# ── What kind a memory is ───────────────────────────────────────────────────


def _explicit(m) -> bool:
    props = m.properties or {}
    return (
        props.get("fact_type") == "explicit_save"
        or "explicit_save" in (m.tags or [])
        or m.source_type == "explicit"
    )


def is_rule(m) -> bool:
    return _explicit(m) and bool(_RULE.search(m.content or ""))


def kind_of(m) -> str:
    """``fact``, ``preference``, ``rule``, ``decision`` or ``episode``."""
    props = m.properties or {}
    if props.get("kind") == EPISODE:
        return "episode"
    if is_rule(m):
        return "rule"
    fact_type = props.get("fact_type")
    tags = set(m.tags or [])
    if fact_type in _PREFERENCE_TYPES or (not fact_type and "preference" in tags):
        return "preference"
    if fact_type == "decision" or (not fact_type and "decision" in tags):
        return "decision"
    return "fact"


def _episode_clause():
    from life_graph.models.db import Memory

    return Memory.properties["kind"].astext == EPISODE


def _rule_clause():
    """:func:`is_rule` in SQL."""
    from life_graph.models.db import Memory

    explicit = or_(
        Memory.properties["fact_type"].astext == "explicit_save",
        Memory.tags.any("explicit_save"),
        Memory.source_type == "explicit",
    )
    return and_(explicit, Memory.content.op("~*")(_RULE_SQL))


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def memory_row(m) -> dict[str, Any]:
    from life_graph.api.jarvis import _source
    from life_graph.core.evidence import evidence_of

    return {
        "id": str(m.id),
        "content": m.content,
        "kind": kind_of(m),
        "source": _source(m),
        # Said, read, observed or guessed (core/evidence.py).
        "evidence": evidence_of(
            getattr(m, "source_type", None), getattr(m, "trust_tier", None), m.properties
        ),
        "created_at": _iso(m.created_at),
    }


def day_summary(content: str) -> str:
    """An episode without its "Conversations with Jarvis on Sunday 25 October 2026: " lead."""
    from life_graph.services.episodes import LABEL

    for label in LABEL.values():
        if content.startswith(f"{label} on ") and ": " in content:
            return content.split(": ", 1)[1]
    return content


def day_row(m, *, with_source: bool = True) -> dict[str, Any]:
    props = m.properties or {}
    row = {"id": str(m.id), "date": props.get("date"), "summary": day_summary(m.content or "")}
    if with_source:
        row["source"] = _DAY_SOURCE.get(props.get("source"), "Life Graph")
    return row


# ── The overview's parts ────────────────────────────────────────────────────


def _counts_query(tenant_id: str):
    from life_graph.models.db import Memory

    active = Memory.status == "active"
    return select(
        func.count().filter(active),
        func.count().filter(Memory.status == "pending"),
        func.count().filter(and_(active, _rule_clause())),
        func.count().filter(and_(active, _episode_clause())),
    ).where(Memory.tenant_id == tenant_id, Memory.status.in_(("active", "pending")))


async def _counts(tenant_id: str) -> dict[str, int]:
    from life_graph.storage.database import async_session

    async with async_session() as session:
        total, pending, rules, episodes = (await session.execute(_counts_query(tenant_id))).first()
    total, rules, episodes = int(total or 0), int(rules or 0), int(episodes or 0)
    return {
        "total": total,
        # Facts in the wide sense: what is remembered, less the rules and the days.
        "facts": max(0, total - rules - episodes),
        "rules": rules,
        "to_review": int(pending or 0),
    }


async def _memories(query) -> list[Any]:
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return list((await session.execute(query)).scalars().all())


def _rules_query(tenant_id: str):
    from life_graph.models.db import Memory

    return (
        select(Memory)
        .where(Memory.tenant_id == tenant_id, Memory.status == "active", _rule_clause())
        .order_by(Memory.created_at.desc())
        .limit(MAX_LIST)
    )


def _recent_query(tenant_id: str):
    from life_graph.models.db import Memory

    return (
        select(Memory)
        .where(
            Memory.tenant_id == tenant_id,
            Memory.status == "active",
            # Not "!=": a memory without a kind is NULL there, and is a fact.
            Memory.properties["kind"].astext.is_distinct_from(EPISODE),
        )
        .order_by(Memory.created_at.desc())
        .limit(MAX_LIST)
    )


def _days_query(tenant_id: str):
    from life_graph.models.db import Memory

    return (
        select(Memory)
        .where(Memory.tenant_id == tenant_id, Memory.status == "active", _episode_clause())
        .order_by(Memory.properties["date"].astext.desc(), Memory.created_at.desc())
        .limit(MAX_DAYS)
    )


async def _entities(tenant_id: str) -> list[dict[str, Any]]:
    from life_graph.models.assistant import Entity
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.id, Entity.key, Entity.name, Entity.mentions)
                .where(Entity.tenant_id == tenant_id, Entity.mentions > 0)
                .order_by(Entity.mentions.desc(), Entity.name)
                .limit(MAX_ENTITIES)
            )
        ).all()
    return [{"id": str(i), "key": k, "name": n, "mentions": int(c or 0)} for i, k, n, c in rows]


async def _contact_names(tenant_id: str) -> list[str]:
    """The owner's contacts' names (enabled accounts), to tell people apart."""
    from life_graph.connectors.base import KIND_CONTACT
    from life_graph.connectors.models import ConnectorAccount, ConnectorItem
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = (
            await session.execute(
                select(ConnectorItem.title)
                .join(ConnectorAccount, ConnectorAccount.id == ConnectorItem.account_id)
                .where(
                    ConnectorItem.tenant_id == tenant_id,
                    ConnectorAccount.enabled.is_(True),
                    ConnectorItem.kind == KIND_CONTACT,
                    ConnectorItem.title.is_not(None),
                )
            )
        ).scalars()
        return [t for t in rows if t]


async def _project_names(tenant_id: str) -> list[str]:
    """Registered projects, and the projects captures came from."""
    from life_graph.models.db import Memory, Project
    from life_graph.storage.database import async_session

    project = Memory.properties["project"].astext
    async with async_session() as session:
        registered = (
            await session.execute(select(Project.name).where(Project.tenant_id == tenant_id))
        ).scalars()
        names = [n for n in registered if n]
        captured = (
            await session.execute(
                select(project)
                .where(Memory.tenant_id == tenant_id, project.is_not(None))
                .distinct()
                .limit(MAX_ENTITIES)
            )
        ).scalars()
        names += [n for n in captured if n]
    return names


def person_keys(names: Iterable[str]) -> set[str]:
    """Entity keys a contact list makes people: full names, and first names."""
    from life_graph.services.entities import normalize

    keys: set[str] = set()
    for name in names:
        key = normalize(name)
        if not key:
            continue
        keys.add(key)
        first = key.split(" ", 1)[0]
        if len(first) >= MIN_FIRST_NAME and not first.isdigit():
            keys.add(first)
    return keys


def project_keys(names: Iterable[str]) -> set[str]:
    """Entity keys of projects, by name and by the last part of a path or repo."""
    from life_graph.services.entities import normalize

    keys: set[str] = set()
    for name in names:
        tail = re.split(r"[\\/]", str(name).strip().rstrip("/\\"))[-1]
        keys.update(k for k in (normalize(name), normalize(tail)) if k)
    return keys


def classify(
    entities: list[dict[str, Any]], people: set[str], projects: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """People, projects and things, most mentioned first. A name that is both
    a project and a contact is a project: projects are named on purpose."""
    out: dict[str, list[dict[str, Any]]] = {"people": [], "projects": [], "things": []}
    for e in entities:
        group = "projects" if e["key"] in projects else "people" if e["key"] in people else "things"
        out[group].append({"id": e["id"], "name": e["name"], "mentions": e["mentions"]})
    return out


async def _groups(tenant_id: str) -> dict[str, list[dict[str, Any]]]:
    entities = await _entities(tenant_id)
    contacts = await _read("contacts", lambda: _contact_names(tenant_id)) or []
    projects = await _read("projects", lambda: _project_names(tenant_id)) or []
    return classify(entities, person_keys(contacts), project_keys(projects))


async def collect(tenant_id: str) -> dict[str, Any]:
    """Every part, each read on its own; a failed one is None."""
    return {
        "counts": await _read("counts", lambda: _counts(tenant_id)),
        "groups": await _read("entities", lambda: _groups(tenant_id)),
        "rules": await _read("rules", lambda: _memories(_rules_query(tenant_id))),
        "recent": await _read("recent", lambda: _memories(_recent_query(tenant_id))),
        "days": await _read("days", lambda: _memories(_days_query(tenant_id))),
    }


def _part(name: str, fn: Callable[[], Any], default: Any) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a malformed row empties its part only
        logger.debug("memory: %s could not be built (%s)", name, type(exc).__name__)
        return default


def assemble(src: dict[str, Any]) -> dict[str, Any]:
    """The overview from the parts (None = that part failed)."""
    counts = src.get("counts") or {}
    groups = src.get("groups")
    return {
        "counts": {
            "total": counts.get("total"),
            "people": None if groups is None else len(groups["people"]),
            "projects": None if groups is None else len(groups["projects"]),
            "facts": counts.get("facts"),
            "rules": counts.get("rules"),
            "to_review": counts.get("to_review"),
        },
        "people": (groups or {}).get("people", [])[:MAX_LIST],
        "projects": (groups or {}).get("projects", [])[:MAX_LIST],
        "things": (groups or {}).get("things", [])[:MAX_LIST],
        "rules": _part(
            "rules",
            lambda: [
                {"id": str(m.id), "content": m.content, "created_at": _iso(m.created_at)}
                for m in src.get("rules") or []
            ],
            [],
        ),
        "recent": _part("recent", lambda: [memory_row(m) for m in src.get("recent") or []], []),
        "days": _part("days", lambda: [day_row(m) for m in src.get("days") or []], []),
    }


async def overview(tenant_id: str) -> dict[str, Any]:
    return assemble(await collect(tenant_id))


# ── Search ──────────────────────────────────────────────────────────────────


class SearchUnavailableError(RuntimeError):
    """No embedding for the query: the meaning search cannot run."""


async def search(query: str, limit: int = SEARCH_DEFAULT) -> list[dict[str, Any]]:
    """Active memories for *query*: the hybrid search memory_search uses
    (tools/memory_search.py), in the request's tenant. Blank asks nothing."""
    from life_graph.api.dependencies import get_memory_manager, get_store

    query = " ".join((query or "").split())
    if not query:
        return []
    embedding = await get_memory_manager().generate_embedding(query)
    if not embedding:
        raise SearchUnavailableError
    hits = await get_store().hybrid_search(
        embedding=embedding,
        query_text=query,
        limit=max(1, min(int(limit), SEARCH_MAX)),
        statuses=("active",),
    )
    return [{**memory_row(m), "score": round(float(score), 4)} for m, score in hits]


# ── One entity ──────────────────────────────────────────────────────────────


async def _entity(tenant_id: str, entity_id: uuid.UUID):
    from life_graph.models.assistant import Entity
    from life_graph.storage.database import async_session

    async with async_session() as session:
        return (
            await session.execute(
                select(Entity).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()


async def _related(tenant_id: str, entity_id: uuid.UUID, memory_ids: list) -> list[dict]:
    """The entities most often mentioned in the same memories."""
    from life_graph.models.assistant import Entity, MemoryEntity
    from life_graph.storage.database import async_session

    if not memory_ids:
        return []
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.id, Entity.name)
                .join(MemoryEntity, MemoryEntity.entity_id == Entity.id)
                .where(
                    MemoryEntity.tenant_id == tenant_id,
                    Entity.tenant_id == tenant_id,
                    MemoryEntity.memory_id.in_(memory_ids),
                    Entity.id != entity_id,
                )
            )
        ).all()
    counts = Counter((str(i), n) for i, n in rows)
    return [{"id": i, "name": n} for (i, n), _ in counts.most_common(MAX_RELATED)]


def also_called(entity, memories: list[Any]) -> list[str]:
    """Other ways the memories write this entity's name ("Life-Graph", "life graph")."""
    from life_graph.services.entities import normalize

    seen: dict[str, None] = {}
    for m in memories:
        for name in (m.properties or {}).get("entities") or []:
            name = str(name).strip()
            if name and name != entity.name and normalize(name) == entity.key:
                seen.setdefault(name)
    return list(seen)


async def entity_detail(tenant_id: str, entity_id: uuid.UUID) -> dict[str, Any] | None:
    """One entity with what is remembered about it, or None when it is not this tenant's."""
    from life_graph.services import entities

    entity = await _entity(tenant_id, entity_id)
    if entity is None:
        return None
    found = await _read(
        "entity memories",
        lambda: entities.memories_for(tenant_id, [entity.id], limit=MAX_ENTITY_MEMORIES),
    )
    found = found or []
    related = await _read("related", lambda: _related(tenant_id, entity.id, [m.id for m in found]))
    episodes = [m for m in found if (m.properties or {}).get("kind") == EPISODE]
    facts = [m for m in found if (m.properties or {}).get("kind") != EPISODE]
    return {
        "id": str(entity.id),
        "name": entity.name,
        "also_called": _part("also_called", lambda: also_called(entity, found), []),
        "mentions": int(entity.mentions or 0),
        "memories": _part("memories", lambda: [memory_row(m) for m in facts[:MAX_LIST]], []),
        "related": related or [],
        "days": _part(
            "days", lambda: [day_row(m, with_source=False) for m in episodes[:MAX_DAYS]], []
        ),
    }
