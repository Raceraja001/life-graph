"""The people, projects and things the owner's memories mention, and what is known about each.

Why not the Apache AGE graph: on 2026-10-22 it served almost no retrieval
(entity search needed the whole question to be a substring of a name, the
neighbour step queried a label nothing wrote, vertices had no tenant). The
extractor already names the entities of every fact (``properties.entities``),
so this keeps a plain tenant-scoped index (migration 053):

* :func:`link` records which entities a memory mentions, under a normalised
  key, so "Life-Graph", "life graph" and "Life Graph" are one thing;
* :func:`known_in_text` finds already-known entities named in a question;
* :func:`memories_for` / :func:`about` give everything remembered about one,
  plus the entities most often mentioned with it.

Generic words the extractor tends to list ("user", "merge", "app") are not
entities and are dropped (:data:`NOT_ENTITIES`).

One person, many names (migration 057, core/aliases.py): an entity may point at
the entity it is another name for (``canonical_id``). Links are learned only from
the owner's explicit statements ("Mahalakshmi (Maha)", "I call her Ma") or from
a shared one-person role with fitting names ("my wife Ma" / "my wife
Mahalakshmi"). A question naming any of the names, or the role ("my wife"), gets
the whole group (:func:`known_in_text`), and a family slot is filed under the
name the group is known by (:func:`canonical_slot`). Two people who only share
a first name are never linked; an unclear case becomes an ``entity_alias``
approval. Nothing is deleted: undoing a link clears ``canonical_id``
(:func:`unlink_alias`).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from life_graph.storage.database import async_session

if TYPE_CHECKING:
    import uuid

#: Words that name nothing in particular. Seen on 2026-10-23 among the
#: extractor's entities: "user" (3), "merge" (3), and the like.
NOT_ENTITIES = frozenset(
    [
        "user",
        "users",
        "owner",
        "assistant",
        "ai",
        "agent",
        "agents",
        "app",
        "apps",
        "application",
        "system",
        "code",
        "task",
        "tasks",
        "project",
        "projects",
        "model",
        "models",
        "tool",
        "tools",
        "feature",
        "features",
        "merge",
        "pr",
        "prs",
        "commit",
        "branch",
        "test",
        "tests",
        "api",
        "apis",
        "data",
        "database",
        "server",
        "file",
        "files",
        "page",
        "pages",
        "plan",
        "work",
        "job",
        "memory",
        "memories",
        "note",
        "notes",
        "question",
        "answer",
        "today",
        "tomorrow",
        "yesterday",
        "week",
        "month",
    ]
)
MAX_KEY = 200
_CACHE_SECONDS = 60.0
#: Per tenant: (key, id, name, canonical_id, role) of each entity, longest key first.
_Row = tuple[str, "uuid.UUID", str, "uuid.UUID | None", "str | None"]
_cache: dict[str, tuple[float, list[_Row]]] = {}
#: Links followed to find the name a group is known by; a longer chain is a loop.
#: Linking never re-points other names (:func:`_link`), so a chain grows by one
#: each time a name that others point at is linked onward.
MAX_HOPS = 20


def normalize(name: str) -> str:
    """The key an entity is stored under: lower case, separators as spaces, no "the"."""
    key = re.sub(r"[-_./\\]+", " ", (name or "").lower())
    key = re.sub(r"[^\w+# ]+", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    key = re.sub(r"^the ", "", key)
    return key[:MAX_KEY]


def is_entity(key: str) -> bool:
    return len(key) >= 2 and not key.isdigit() and key not in NOT_ENTITIES


async def link(tenant_id: str, memory_id: uuid.UUID, names: list[str]) -> int:
    """Record that *memory_id* mentions *names*; return how many new links were made."""
    seen: dict[str, str] = {}
    for name in names or []:
        key = normalize(str(name))
        if is_entity(key) and key not in seen:
            seen[key] = str(name).strip()[:MAX_KEY]
    if not seen:
        return 0
    async with async_session() as session:
        linked = 0
        for key, name in seen.items():
            entity_id = await session.scalar(
                text(
                    "INSERT INTO entities (tenant_id, key, name, mentions) "
                    "VALUES (:t, :k, :n, 0) "
                    "ON CONFLICT (tenant_id, key) DO UPDATE SET updated_at = now() "
                    "RETURNING id"
                ),
                {"t": tenant_id, "k": key, "n": name},
            )
            added = await session.scalar(
                text(
                    "INSERT INTO memory_entities (memory_id, entity_id, tenant_id) "
                    "VALUES (:m, :e, :t) ON CONFLICT DO NOTHING RETURNING 1"
                ),
                {"m": memory_id, "e": entity_id, "t": tenant_id},
            )
            if added:
                # Counted per new link, so linking the same memory twice is harmless.
                await session.execute(
                    text("UPDATE entities SET mentions = mentions + 1 WHERE id = :e"),
                    {"e": entity_id},
                )
                linked += 1
        await session.commit()
    _cache.pop(tenant_id, None)
    return linked


async def _known(tenant_id: str) -> list[_Row]:
    """(key, id, name, canonical_id, role) of the tenant's entities, longest key
    first; cached briefly."""
    hit = _cache.get(tenant_id)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    from life_graph.models.assistant import Entity

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.key, Entity.id, Entity.name, Entity.canonical_id, Entity.role).where(
                    Entity.tenant_id == tenant_id
                )
            )
        ).all()
    known = sorted((tuple(r) for r in rows), key=lambda r: -len(r[0]))
    _cache[tenant_id] = (time.monotonic(), known)
    return known


def _roots(rows: list[_Row]) -> dict[uuid.UUID, uuid.UUID]:
    """Each entity's root: where its chain of other names ends (itself when none)."""
    parent = {r[1]: r[3] for r in rows}
    out: dict[uuid.UUID, uuid.UUID] = {}
    for eid in parent:
        node, hops = eid, 0
        while parent.get(node) in parent and hops < MAX_HOPS:
            node, hops = parent[node], hops + 1
        out[eid] = node
    return out


async def known_in_text(tenant_id: str, text_: str) -> list[tuple[uuid.UUID, str]]:
    """Known entities named in *text_* (whole words), as (id, name), then the other
    names of each (migration 057): "Maha" also brings "Mahalakshmi". A one-person
    role in the question ("my wife", "amma") brings the person who holds it."""
    from life_graph.core import aliases

    padded = f" {normalize(text_)} "
    rows = await _known(tenant_id)
    hits = [r for r in rows if f" {r[0]} " in padded or f" {r[0]}s " in padded]
    roles = aliases.roles_in_question(text_)
    if roles:
        hits += [r for r in rows if r[4] in roles and r[3] is None and r not in hits]
    if not hits:
        return []
    found = [(r[1], r[2]) for r in hits]
    if any(r[3] for r in rows):
        roots = _roots(rows)
        groups = {roots[r[1]] for r in hits}
        found += [(r[1], r[2]) for r in rows if roots[r[1]] in groups and r not in hits]
    return found


def alias_hint(tenant_id: str, named: list[tuple[uuid.UUID, str]]) -> str:
    """ "Names: Maha = Mahalakshmi (the owner's spouse)" for the groups among *named*
    that have other names or a role; "" otherwise. Reads only the cache that
    :func:`known_in_text` has just filled: never a query."""
    hit = _cache.get(tenant_id)
    if not hit or not named:
        return ""
    rows = hit[1]
    roots = _roots(rows)
    by_id = {r[1]: r for r in rows}
    groups: list[uuid.UUID] = []
    for eid, _ in named:
        if eid in roots and roots[eid] not in groups:
            groups.append(roots[eid])
    parts = []
    for root in groups:
        members = [r for r in rows if roots[r[1]] == root]
        role = by_id[root][4] or next((r[4] for r in members if r[4]), None)
        names = " = ".join(dict.fromkeys([by_id[root][2], *(r[2] for r in members)]))
        if len(members) < 2 and not role:
            continue
        if role == "owner":
            names += " (the owner)"
        elif role:
            names += f" (the owner's {role})"
        parts.append(names)
    return ("Names: " + "; ".join(parts)) if parts else ""


def _slug(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_")


async def canonical_slot(tenant_id: str, slot: str) -> str:
    """*slot* with a family member's name (or one-person role) replaced by the name
    their group is known by: ``family.maha.birthday`` → ``family.mahalakshmi.birthday``,
    and ``family.spouse.birthday`` the same once the spouse is known.
    ``family.spouse`` itself (the spouse's name) is kept."""
    parts = (slot or "").split(".")
    if len(parts) < 3 or parts[0] != "family":
        return slot
    from life_graph.core import aliases

    rows = await _known(tenant_id)
    if not rows:
        return slot
    by_id = {r[1]: r for r in rows}
    roots = _roots(rows)
    seg = parts[1]
    root = None
    if seg in aliases.UNIQUE_ROLES:
        holders = [r for r in rows if r[4] == seg and r[3] is None]
        if len(holders) == 1:
            root = holders[0][1]
    else:
        match = next((r for r in rows if _slug(r[0]) == seg), None)
        if match is not None:
            root = roots[match[1]]
    if root is None:
        return slot
    name = _slug(by_id[root][0])
    if not name or name == seg:
        return slot
    return ".".join([parts[0], name, *parts[2:]])[:80]


async def other_names(tenant_id: str, slug: str) -> list[str]:
    """The other names of the person a family slot is filed under (for the card)."""
    rows = await _known(tenant_id)
    if not any(r[3] for r in rows):
        return []
    match = next((r for r in rows if _slug(r[0]) == slug), None)
    if match is None:
        return []
    roots = _roots(rows)
    root = roots[match[1]]
    return [r[2] for r in rows if roots[r[1]] == root and r[1] != match[1]]


async def memories_for(tenant_id: str, entity_ids: list[uuid.UUID], limit: int = 20) -> list[Any]:
    """Active memories that mention any of *entity_ids*, newest first."""
    if not entity_ids:
        return []
    from life_graph.models.assistant import MemoryEntity
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .join(MemoryEntity, MemoryEntity.memory_id == Memory.id)
                    .where(
                        MemoryEntity.tenant_id == tenant_id,
                        MemoryEntity.entity_id.in_(entity_ids),
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                    )
                    .order_by(Memory.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .unique()
            .all()
        )
    return list(rows)


async def about(tenant_id: str, name: str, limit: int = 20) -> dict[str, Any] | None:
    """Everything remembered about one entity, and what it is most often mentioned with.

    *name* is matched on its key first, then as a whole-word part of a longer
    key ("school" finds "school app"). None when nothing is known by that name.
    """
    from life_graph.models.assistant import Entity, MemoryEntity

    key = normalize(name)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.id, Entity.key, Entity.name).where(
                    Entity.tenant_id == tenant_id,
                    (Entity.key == key)
                    | Entity.key.like(f"{key} %")
                    | Entity.key.like(f"% {key}")
                    | Entity.key.like(f"% {key} %"),
                )
            )
        ).all()
    if not rows:
        return None
    ids = [r[0] for r in rows]
    # The other names of the same person (migration 057): "about Maha" is about
    # Mahalakshmi too.
    known = await _known(tenant_id)
    if any(r[3] for r in known):
        roots = _roots(known)
        groups = {roots.get(i) for i in ids}
        extra = [r for r in known if roots[r[1]] in groups and r[1] not in ids]
        rows = [*rows, *((r[1], r[0], r[2]) for r in extra)]
        ids += [r[1] for r in extra]
    memories = await memories_for(tenant_id, ids, limit=limit)
    related: Counter[str] = Counter()
    if memories:
        async with async_session() as session:
            co = (
                await session.execute(
                    select(Entity.name)
                    .join(MemoryEntity, MemoryEntity.entity_id == Entity.id)
                    .where(
                        MemoryEntity.tenant_id == tenant_id,
                        MemoryEntity.memory_id.in_([m.id for m in memories]),
                        Entity.id.notin_(ids),
                    )
                )
            ).all()
        related.update(r[0] for r in co)
    # The entity the name is exactly, else the first it is part of: the phone
    # opens it from Jarvis's answer (GET /jarvis/entities/{id}).
    exact = next((r[0] for r in rows if r[1] == key), rows[0][0])
    return {
        "id": exact,
        "names": [r[2] for r in rows],
        "memories": memories,
        "related": [n for n, _ in related.most_common(8)],
    }


# ── Learning other names (migration 057, core/aliases.py) ─────────────────


async def _entity(session: Any, tenant_id: str, name: str) -> Any | None:
    """The tenant's entity for *name*, created when new; None for a non-entity."""
    from life_graph.models.assistant import Entity

    key = normalize(name)
    if not is_entity(key):
        return None
    entity_id = await session.scalar(
        text(
            "INSERT INTO entities (tenant_id, key, name, mentions) VALUES (:t, :k, :n, 0) "
            "ON CONFLICT (tenant_id, key) DO UPDATE SET updated_at = now() RETURNING id"
        ),
        {"t": tenant_id, "k": key, "n": name.strip()[:MAX_KEY]},
    )
    return await session.get(Entity, entity_id)


async def _root_of(session: Any, entity: Any) -> Any:
    from life_graph.models.assistant import Entity

    node, hops = entity, 0
    while node.canonical_id and hops < MAX_HOPS:
        parent = await session.get(Entity, node.canonical_id)
        if parent is None:
            break
        node, hops = parent, hops + 1
    return node


async def _queue(
    session: Any,
    tenant_id: str,
    alias: Any,
    canonical: Any,
    *,
    applied: bool,
    why: str,
    role_copied: bool = False,
) -> None:
    """An ``entity_alias`` approval: *applied* (the link is made; reject undoes it)
    or suggested (approve makes it). Asked once per pair, whatever the answer."""
    from life_graph.models.db import Approval

    ref = f"{alias.id}|{canonical.id}"
    exists = await session.scalar(
        select(Approval.id).where(
            Approval.tenant_id == tenant_id,
            Approval.source == "entities",
            Approval.source_ref == ref,
        )
    )
    if exists:
        return
    title = (
        f"Linked the name '{alias.name}' to '{canonical.name}'"
        if applied
        else f"Is '{alias.name}' the same person as '{canonical.name}'?"
    )
    session.add(
        Approval(
            tenant_id=tenant_id,
            kind="entity_alias",
            source="entities",
            source_ref=ref,
            title=title[:200],
            detail=why[:500],
            payload={
                "alias_id": str(alias.id),
                "canonical_id": str(canonical.id),
                # What reject restores for an applied link (None: its own person).
                "previous_canonical_id": None,
                # The link gave *canonical* the alias's role: reject takes it back.
                "role_copied": role_copied,
                "applied": applied,
            },
        )
    )


async def _link(session: Any, alias: Any, root: Any, via: str, evidence: str) -> bool:
    """Point *alias* at *root*; True when *alias*'s role was copied to *root*.

    Only *alias* changes: names that point at *alias* keep pointing at it and
    reach *root* through it (every reader follows the chain, :func:`_roots`,
    :func:`_root_of`). Until the review of PR #205 they were re-pointed at
    *root*, and rejecting the link freed *alias* but left them on *root*."""
    alias.canonical_id = root.id
    alias.alias_via = via
    alias.alias_evidence = evidence[:300] or None
    if alias.role and not root.role:
        root.role = alias.role
        return True
    return False


async def learn_aliases(tenant_id: str, text_: str, *, evidence: str = "") -> dict[str, int]:
    """Learn other names and roles from the owner's own words in *text_*.

    The caller passes only affirmed, firm text in the owner's words (trust tier
    ``self``). Returns counts: ``linked``, ``held`` (asked of the owner) and
    ``roles`` (roles newly recorded).
    """
    from life_graph.core import aliases
    from life_graph.models.assistant import Entity

    claims, roles = aliases.parse(text_ or "")
    counts = {"linked": 0, "held": 0, "roles": 0}
    if not claims and not roles:
        return counts
    evidence = " ".join((evidence or text_).split())[:300]
    async with async_session() as session:
        for claim in claims:
            full = await _entity(session, tenant_id, claim.full)
            alias = await _entity(session, tenant_id, claim.alias)
            if full is None or alias is None or full.id == alias.id:
                continue
            root = await _root_of(session, full)
            current = await _root_of(session, alias)
            if current.id == root.id:
                continue  # already one person
            if alias.canonical_id is None:
                await _link(session, alias, root, "said", evidence)
                counts["linked"] += 1
            else:
                # "Priya" already names someone else (the second Priya): ask, never guess.
                await _queue(
                    session,
                    tenant_id,
                    alias,
                    root,
                    applied=False,
                    why=f"'{alias.name}' is linked to '{current.name}' now. Said: {evidence}",
                )
                counts["held"] += 1
        for claim in roles:
            ent = await _entity(session, tenant_id, claim.name)
            if ent is None:
                continue
            root = await _root_of(session, ent)
            if root.role is None:
                root.role = claim.role
                counts["roles"] += 1
            if claim.role not in aliases.UNIQUE_ROLES or root.role != claim.role:
                continue
            await session.flush()
            others = (
                (
                    await session.execute(
                        select(Entity).where(
                            Entity.tenant_id == tenant_id,
                            Entity.role == claim.role,
                            Entity.canonical_id.is_(None),
                            Entity.id != root.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for other in others:
                why = f"Both are the owner's {claim.role}. Said: {evidence}"
                if aliases.compatible(other.name, root.name):
                    # "Ma" and "Mahalakshmi": the shorter is the other name.
                    short, long_ = sorted((other, root), key=lambda e: len(e.name))
                    copied = await _link(session, short, long_, "role", evidence)
                    await _queue(
                        session,
                        tenant_id,
                        short,
                        long_,
                        applied=True,
                        why=why,
                        role_copied=copied,
                    )
                    counts["linked"] += 1
                    root = long_
                else:
                    await _queue(session, tenant_id, other, root, applied=False, why=why)
                    counts["held"] += 1
        await session.commit()
    _cache.pop(tenant_id, None)
    return counts


async def set_alias(
    session: Any, tenant_id: str, alias_id: Any, canonical_id: Any, *, via: str | None
) -> bool:
    """Point one entity at another (or at nothing: ``canonical_id=None``) in the
    caller's transaction. The approvals path uses it to apply or undo a link."""
    import uuid as _uuid

    from life_graph.models.assistant import Entity

    try:
        ent = await session.get(Entity, _uuid.UUID(str(alias_id)))
    except ValueError:
        return False
    if ent is None or ent.tenant_id != tenant_id:
        return False
    if canonical_id is not None:
        target = await session.get(Entity, _uuid.UUID(str(canonical_id)))
        if target is None or target.tenant_id != tenant_id:
            return False
        root = await _root_of(session, target)
        if root.id == ent.id:
            return False  # would make a loop
        await _link(session, ent, root, via or "approved", ent.alias_evidence or "")
    else:
        ent.canonical_id = None
        ent.alias_via = None
    _cache.pop(tenant_id, None)
    return True


async def undo_link(session: Any, tenant_id: str, payload: dict[str, Any]) -> bool:
    """Undo an applied ``entity_alias`` link (the owner rejected it) in the caller's
    transaction: the alias points where it did before, and a role the link copied
    onto the other name is taken back. Names pointing at the alias stay with it
    (:func:`_link` never moves them), so they leave the group with it."""
    import uuid as _uuid

    from life_graph.models.assistant import Entity

    alias_id, canonical_id = payload.get("alias_id"), payload.get("canonical_id")
    if payload.get("role_copied") and alias_id and canonical_id:
        try:
            alias = await session.get(Entity, _uuid.UUID(str(alias_id)))
            target = await session.get(Entity, _uuid.UUID(str(canonical_id)))
        except ValueError:
            alias = target = None
        if (
            alias is not None
            and target is not None
            and alias.tenant_id == tenant_id == target.tenant_id
            and target.role == alias.role
        ):
            target.role = None
    return await set_alias(
        session, tenant_id, alias_id, payload.get("previous_canonical_id"), via="approved"
    )


async def unlink_alias(tenant_id: str, entity_id: Any) -> bool:
    """Undo a link: *entity_id* is its own person again. Nothing else changes."""
    async with async_session() as session:
        done = await set_alias(session, tenant_id, entity_id, None, via=None)
        await session.commit()
    return done
