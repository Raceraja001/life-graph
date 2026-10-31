"""The "What Jarvis knows about me" page: see the memory, and fix it.

One read (:func:`overview`) gives the page everything it shows: what waits for
review, the owner's form (slotted facts by topic, each with its earlier values),
the other active notes, and the cold tier (archived and replaced memories,
labelled as memory_tiers labels them). :func:`connections` gives one memory's
links and the people and things it mentions.

The fixes reuse the paths that already exist, so the page cannot do what the
rest of Life Graph would not:

- Keep / Drop a pending memory: api/memories.py ``_transition``.
- Correct: the pieces of ``memory_save`` with ``replaces_id``
  (tools/memory_search.py): the new memory supersedes the old one, a
  "You corrected a memory" approval is filed (rejecting it restores the old
  one), and api/jarvis.py's undo takes the correction back.
- Archive / Bring back / Drop an active memory: a status change with a note in
  ``properties``; nothing is ever deleted. A Drop is the owner taking the memory
  back (``forgotten``, the memory_forget shape), so the cold tier never shows it.

No model call anywhere here: the text filter is a substring match, so the page
works while the GPU is busy or the embedding service is down.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import defer

from life_graph.core import evidence as ev
from life_graph.core import slots
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)

PENDING_MAX = 50
#: Active memories read for the form and the notes (filtered in Python after).
ACTIVE_SCAN = 3000
NOTES_DEFAULT = 100
NOTES_MAX = 500
COLD_DEFAULT = 50
COLD_MAX = 300
HISTORY_MAX = 300
LINKS_MAX = 20
MAX_CORRECTION_CHARS = 1000
KINDS = ("fact", "preference", "rule", "decision", "episode")

#: Owner actions recorded in properties: who did it, from where.
_BY = {"by": "owner", "surface": "memory_page"}


class PageActionError(Exception):
    """An action that cannot apply: ``status`` is the HTTP code to answer with."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _evidence(m: Any) -> str:
    return ev.evidence_of(
        getattr(m, "source_type", None), getattr(m, "trust_tier", None), m.properties or {}
    )


def row(m: Any) -> dict[str, Any]:
    """One memory as the page shows it."""
    from life_graph.api.jarvis import _source
    from life_graph.services.jarvis_memory import kind_of

    props = m.properties or {}
    slot = props.get("slot")
    return {
        "id": str(m.id),
        "content": m.content,
        "status": m.status,
        "kind": kind_of(m),
        "evidence": _evidence(m),
        "source": _source(m),
        "slot": slot,
        "slot_label": slots.label(slot) if slot else None,
        "topic": slots.topic_of(slot) if slot else None,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(getattr(m, "updated_at", None)),
        "confidence": getattr(m, "confidence", None),
        "importance": getattr(m, "importance", None),
        # Only the owner's own corrections can be undone from the page.
        "undoable": props.get("saved_by") in ("jarvis", "owner") and bool(props.get("replaces_id")),
    }


def _matches(m: Any, q: str) -> bool:
    return not q or q in (m.content or "").casefold()


def _cold_clause(tenant_id: str):
    """memory_tiers.filters() in SQLAlchemy: archived or replaced, not taken back,
    not a bulk clean-up, not from before the owner's fresh start."""
    from life_graph.config import settings
    from life_graph.models.db import Memory
    from life_graph.services.memory_tiers import BULK_ARCHIVES, COLD_STATUSES

    clauses = [
        Memory.tenant_id == tenant_id,
        Memory.status.in_(COLD_STATUSES),
        ~Memory.properties.has_key("forgotten"),
        ~Memory.properties.has_key("undone"),
        func.coalesce(Memory.properties["archived_by"].astext, "").notin_(BULK_ARCHIVES),
    ]
    start = settings.memory_start()
    if start is not None:
        clauses.append(Memory.created_at >= start)
    return and_(*clauses)


async def _replacements(session, tenant_id: str, ids: list[Any]) -> dict[Any, tuple]:
    """superseded_by id -> (created_at, corrected?) of the memory that replaced it."""
    from life_graph.models.db import Memory

    ids = [i for i in ids if i]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Memory.id, Memory.created_at, Memory.properties).where(
                Memory.id.in_(ids), Memory.tenant_id == tenant_id
            )
        )
    ).all()
    return {
        r[0]: (r[1], bool((r[2] or {}).get("correction") or (r[2] or {}).get("replaces_id")))
        for r in rows
    }


def _cold_label(m: Any, replaced: dict[Any, tuple]) -> str:
    from life_graph.services import memory_tiers

    if m.superseded_by in replaced:
        m.replaced = replaced[m.superseded_by]
    return memory_tiers.label(m)


def _history_row(m: Any, replaced: dict[Any, tuple]) -> dict[str, Any]:
    when, corrected = replaced.get(m.superseded_by, (m.updated_at, False))
    return {
        "id": str(m.id),
        "content": m.content,
        "until": _iso(when or m.updated_at),
        "how": "corrected" if corrected else "replaced",
    }


async def overview(
    tenant_id: str,
    *,
    q: str = "",
    kind: str | None = None,
    evidence: str | None = None,
    topic: str | None = None,
    notes_limit: int = NOTES_DEFAULT,
    cold_limit: int = COLD_DEFAULT,
) -> dict[str, Any]:
    """Everything the page shows, for *tenant_id*. ``q`` narrows notes, the form and
    the cold tier by substring; ``kind``/``evidence`` narrow notes; ``topic`` the form."""
    from life_graph.models.db import Memory
    from life_graph.services.jarvis_memory import kind_of

    q = " ".join((q or "").split()).casefold()
    notes_limit = max(1, min(int(notes_limit), NOTES_MAX))
    cold_limit = max(0, min(int(cold_limit), COLD_MAX))
    now = datetime.now(UTC)
    lite = defer(Memory.embedding)

    async with async_session() as session:
        pending_where = (Memory.tenant_id == tenant_id, Memory.status == "pending")
        pending_total = await session.scalar(
            select(func.count()).select_from(Memory).where(*pending_where)
        )
        pending = (
            (
                await session.execute(
                    select(Memory)
                    .where(*pending_where)
                    .options(lite)
                    .order_by(Memory.created_at.desc())
                    .limit(PENDING_MAX)
                )
            )
            .scalars()
            .all()
        )
        active = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                        or_(Memory.valid_until.is_(None), Memory.valid_until > now),
                    )
                    .options(lite)
                    .order_by(Memory.created_at.desc())
                    .limit(ACTIVE_SCAN)
                )
            )
            .scalars()
            .all()
        )
        history = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.status == "superseded",
                        Memory.properties["slot"].astext.isnot(None),
                    )
                    .options(lite)
                    .order_by(Memory.updated_at.desc())
                    .limit(HISTORY_MAX)
                )
            )
            .scalars()
            .all()
        )
        cold_where = _cold_clause(tenant_id)
        if q:
            cold_where = and_(cold_where, Memory.content.ilike(f"%{_like(q)}%", escape="\\"))
        cold_total = await session.scalar(
            select(func.count()).select_from(Memory).where(cold_where)
        )
        cold = (
            (
                await session.execute(
                    select(Memory)
                    .where(cold_where)
                    .options(lite)
                    .order_by(Memory.updated_at.desc())
                    .limit(cold_limit)
                )
            )
            .scalars()
            .all()
            if cold_limit
            else []
        )
        replaced = await _replacements(
            session, tenant_id, [m.superseded_by for m in [*history, *cold]]
        )

    by_slot: dict[str, list[dict[str, Any]]] = {}
    for m in history:
        by_slot.setdefault((m.properties or {})["slot"], []).append(_history_row(m, replaced))

    form_rows = [m for m in active if (m.properties or {}).get("slot")]
    note_rows = [m for m in active if not (m.properties or {}).get("slot")]

    topics: dict[str, list[dict[str, Any]]] = {}
    for m in sorted(form_rows, key=lambda m: (m.properties or {})["slot"]):
        slot = m.properties["slot"]
        t = slots.topic_of(slot)
        if topic and t != topic:
            continue
        if q and not (_matches(m, q) or q in slot.casefold()):
            continue
        topics.setdefault(t, []).append({**row(m), "history": by_slot.get(slot, [])})
    order = {t: n for n, t in enumerate(slots.TOPICS)}
    form = [
        {"topic": t, "items": items}
        for t, items in sorted(topics.items(), key=lambda kv: order.get(kv[0], len(order)))
    ]

    notes = [
        m
        for m in note_rows
        if _matches(m, q)
        and (not evidence or _evidence(m) == evidence)
        and (not kind or kind_of(m) == kind)
    ]
    return {
        "counts": {
            "active": len(active),
            "form": len(form_rows),
            "notes": len(note_rows),
            "pending": int(pending_total or 0),
            "older": int(cold_total or 0) if not q else None,
        },
        "pending": [row(m) for m in pending],
        "pending_total": int(pending_total or 0),
        "form": form,
        "notes": [row(m) for m in notes[:notes_limit]],
        "notes_total": len(notes),
        "cold": [{**row(m), "label": _cold_label(m, replaced)} for m in cold],
        "cold_total": int(cold_total or 0),
        "topics": list(slots.TOPICS),
        "kinds": list(KINDS),
        "evidence_kinds": list(ev.KINDS),
        "truncated": len(active) >= ACTIVE_SCAN,
    }


def _like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── Connections ─────────────────────────────────────────────────────────────


async def _get(session, tenant_id: str, memory_id: uuid.UUID):
    from life_graph.models.db import Memory

    return (
        await session.execute(
            select(Memory)
            .where(Memory.id == memory_id, Memory.tenant_id == tenant_id)
            .options(defer(Memory.embedding))
        )
    ).scalar_one_or_none()


async def connections(tenant_id: str, memory_id: uuid.UUID) -> dict[str, Any] | None:
    """One memory's links (ASSOCIATED, strength now), what it replaced or was
    replaced by, and the entities it mentions. None when it is not this tenant's."""
    from life_graph.models.assistant import Entity, MemoryEntity
    from life_graph.models.db import Memory
    from life_graph.services.associations import _EFFECTIVE, HALF_LIFE_DAYS, LINK_TYPE

    async with async_session() as session:
        m = await _get(session, tenant_id, memory_id)
        if m is None:
            return None
        links = (
            await session.execute(
                text(
                    f"""
                    SELECT CASE WHEN l.source_memory_id = :id THEN l.target_memory_id
                                ELSE l.source_memory_id END AS other,
                           l.strength AS stored, {_EFFECTIVE} AS s
                    FROM memory_links l
                    WHERE l.tenant_id = :t AND l.link_type = '{LINK_TYPE}'
                      AND (l.source_memory_id = :id OR l.target_memory_id = :id)
                    ORDER BY s DESC
                    LIMIT :n
                    """
                ),
                {"id": memory_id, "t": tenant_id, "half_life": HALF_LIFE_DAYS, "n": LINKS_MAX},
            )
        ).all()
        strength = {r[0]: (float(r[2]), float(r[1])) for r in links}
        chain_ids = [i for i in (m.supersedes, m.superseded_by) if i]
        others = (
            (
                await session.execute(
                    select(Memory)
                    .where(
                        Memory.tenant_id == tenant_id,
                        Memory.id.in_([*strength, *chain_ids]),
                        Memory.status != "rejected",
                        # Taken back by the owner: never shown again, here either.
                        text(
                            "NOT (COALESCE(memories.properties, '{}'::jsonb)"
                            " ?| ARRAY['forgotten', 'undone'])"
                        ),
                    )
                    .options(defer(Memory.embedding))
                )
            )
            .scalars()
            .all()
            if strength or chain_ids
            else []
        )
        entities = (
            await session.execute(
                select(Entity.id, Entity.name, Entity.mentions)
                .join(MemoryEntity, MemoryEntity.entity_id == Entity.id)
                .where(
                    MemoryEntity.tenant_id == tenant_id,
                    Entity.tenant_id == tenant_id,
                    MemoryEntity.memory_id == memory_id,
                )
                .order_by(Entity.mentions.desc(), Entity.name)
            )
        ).all()

    by_id = {o.id: o for o in others}
    linked = [
        {**row(by_id[i]), "strength": round(s, 3), "stored_strength": round(st, 3)}
        for i, (s, st) in sorted(strength.items(), key=lambda kv: -kv[1][0])
        if i in by_id
    ]
    return {
        "memory": row(m),
        "linked": linked,
        "replaces": row(by_id[m.supersedes]) if m.supersedes in by_id else None,
        "replaced_by": row(by_id[m.superseded_by]) if m.superseded_by in by_id else None,
        "entities": [{"id": str(i), "name": n, "mentions": int(c or 0)} for i, n, c in entities],
    }


# ── Actions ─────────────────────────────────────────────────────────────────


async def _set_status(
    tenant_id: str, memory_id: uuid.UUID, *, from_: tuple[str, ...], to: str, note: dict
) -> str | None:
    """Move one of the tenant's memories from *from_* to *to*, merging *note* into its
    properties. Returns the old status, or None when nothing matched."""
    async with async_session() as session:
        old = (
            await session.execute(
                text("SELECT status FROM memories WHERE id = :id AND tenant_id = :t FOR UPDATE"),
                {"id": memory_id, "t": tenant_id},
            )
        ).first()
        if old is None or old[0] not in from_:
            return None
        await session.execute(
            text(
                "UPDATE memories SET status = :to, updated_at = NOW(),"
                " properties = COALESCE(properties, '{}'::jsonb) || CAST(:note AS jsonb)"
                " WHERE id = :id AND tenant_id = :t"
            ),
            {"id": memory_id, "t": tenant_id, "to": to, "note": json.dumps(note)},
        )
        await session.commit()
    _changed(tenant_id)
    return old[0]


def _changed(tenant_id: str) -> None:
    from life_graph.services import profile_card

    profile_card.invalidate(tenant_id)


async def _status_of(tenant_id: str, memory_id: uuid.UUID) -> str | None:
    async with async_session() as session:
        return await session.scalar(
            text("SELECT status FROM memories WHERE id = :id AND tenant_id = :t"),
            {"id": memory_id, "t": tenant_id},
        )


async def _refuse(tenant_id: str, memory_id: uuid.UUID, verb: str) -> PageActionError:
    status = await _status_of(tenant_id, memory_id)
    if status is None:
        return PageActionError(404, "Memory not found.")
    return PageActionError(409, f"Cannot {verb} a {status} memory.")


async def archive(tenant_id: str, memory_id: uuid.UUID) -> dict[str, Any]:
    """Active -> archived by the owner: an older note, still in the cold tier."""
    now = datetime.now(UTC).isoformat()
    note = {"archived_by": "owner", "archived": {"at": now, **_BY}}
    if await _set_status(tenant_id, memory_id, from_=("active",), to="archived", note=note):
        return {"id": str(memory_id), "status": "archived"}
    raise await _refuse(tenant_id, memory_id, "archive")


async def restore(tenant_id: str, memory_id: uuid.UUID) -> dict[str, Any]:
    """Bring back: archived -> active, and nothing else (a replaced memory is history;
    the newer value is the current one). Clears a Drop's ``forgotten`` mark, so a
    dropped-then-restored memory is a plain memory again."""
    async with async_session() as session:
        result = await session.execute(
            text(
                "UPDATE memories SET status = 'active', updated_at = NOW(), last_accessed = NOW(),"
                " properties = (COALESCE(properties, '{}'::jsonb) - 'forgotten')"
                " || CAST(:note AS jsonb)"
                " WHERE id = :id AND tenant_id = :t AND status = 'archived'"
                " AND NOT (COALESCE(properties, '{}'::jsonb) ? 'undone')"
            ),
            {
                "id": memory_id,
                "t": tenant_id,
                "note": json.dumps({"restored": {"at": datetime.now(UTC).isoformat(), **_BY}}),
            },
        )
        await session.commit()
    if result.rowcount:
        _changed(tenant_id)
        return {"id": str(memory_id), "status": "active"}
    raise await _refuse(tenant_id, memory_id, "bring back")


async def drop(tenant_id: str, memory_id: uuid.UUID, store: Any) -> dict[str, Any]:
    """Pending: the review queue's reject. Active: taken back (archived + forgotten),
    never shown or read again; restore undoes it."""
    status = await _status_of(tenant_id, memory_id)
    if status is None:
        raise PageActionError(404, "Memory not found.")
    if status in ("pending", "rejected"):
        from life_graph.api.memories import _transition

        updated = await _transition(memory_id, "reject", store)
        return {"id": str(memory_id), "status": updated.status}
    note = {
        "forgotten": {
            "at": datetime.now(UTC).isoformat(),
            "reason": "dropped on the memory page",
            **_BY,
        }
    }
    if await _set_status(tenant_id, memory_id, from_=("active",), to="archived", note=note):
        # A wrong replacement taken back: the value it replaced is current again,
        # as /jarvis/memories/{id}/undo and a rejected contradiction do.
        await _restore_replaced(tenant_id, memory_id)
        return {"id": str(memory_id), "status": "archived", "forgotten": True}
    raise await _refuse(tenant_id, memory_id, "drop")


async def _restore_replaced(tenant_id: str, memory_id: uuid.UUID) -> None:
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE memories SET status = 'active', superseded_by = NULL, updated_at = NOW()"
                " WHERE tenant_id = :t AND superseded_by = :id AND status = 'superseded'"
                " AND NOT (COALESCE(properties, '{}'::jsonb) ? 'merged_into')"
            ),
            {"id": memory_id, "t": tenant_id},
        )
        await session.commit()
    _changed(tenant_id)


async def correct(tenant_id: str, memory_id: uuid.UUID, content: str) -> dict[str, Any]:
    """The owner's corrected wording for an active memory: memory_save's correction
    path (tools/memory_search.py), the owner having asked by definition.

    The new memory is active at once (the owner typed it), carries the old one's
    slot so the form keeps its field, supersedes the old one, and files the
    "You corrected a memory" approval (rejecting it restores the old one).
    api/jarvis.py's undo takes it back."""
    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.schemas import MemoryCreate
    from life_graph.tools.memory_search import _queue_replacement, _supersede

    text_ = " ".join(str(content or "").split())
    if len(text_) < 3:
        raise PageActionError(422, "Write the corrected memory.")
    if len(text_) > MAX_CORRECTION_CHARS:
        raise PageActionError(422, f"Keep it under {MAX_CORRECTION_CHARS} characters.")

    async with async_session() as session:
        old = await _get(session, tenant_id, memory_id)
    if old is None:
        raise PageActionError(404, "Memory not found.")
    if old.status != "active":
        raise PageActionError(409, f"Cannot correct a {old.status} memory.")
    if " ".join((old.content or "").split()).casefold() == text_.casefold():
        raise PageActionError(422, "That is what it already says.")

    old_props = old.properties or {}
    props: dict[str, Any] = {
        "saved_by": "owner",
        "surface": "dashboard",
        "replaces_id": str(old.id),
        "correction": True,
        **{k: old_props[k] for k in ("slot", "fact_type", "subject") if old_props.get(k)},
    }
    content_hash = hashlib.sha256(text_.lower().encode()).hexdigest()
    with tenant_scope(tenant_id):
        store = get_store()
        same = await store.find_exact_duplicate(content_hash)
        if same is not None and same.status == "active":
            raise PageActionError(409, "Jarvis already remembers exactly that.")
        try:
            embedding = await get_memory_manager().generate_embedding(text_)
        except Exception:  # noqa: BLE001 - stored without; the embed backfill catches up
            logger.warning("Correction stored without an embedding", exc_info=True)
            embedding = None
        new = await store.store(
            MemoryCreate(
                content=text_,
                tags=["explicit_save", "correction"],
                source_type="explicit",
                importance=max(0.7, float(old.importance or 0.0)),
                properties=props,
            ),
            embedding=embedding or None,
            trust_tier="self",
            status="active",
            extraction_tier="explicit",
        )
    replaced = await _supersede(tenant_id, old.id, new.id)
    if replaced is None:
        # Someone else replaced it in between: take this one back, never two values.
        await _set_status(
            tenant_id,
            new.id,
            from_=("active",),
            to="archived",
            note={"undone": {"at": datetime.now(UTC).isoformat(), "reason": "race", **_BY}},
        )
        raise PageActionError(409, "That memory changed meanwhile; reload and try again.")
    await _queue_replacement(tenant_id, old.id, new.id, replaced, applied=True)

    try:
        from life_graph.services import entities

        names = [n for n in (old_props.get("entities") or []) if isinstance(n, str)]
        names += [name for _, name in await entities.known_in_text(tenant_id, text_)]
        await entities.link(tenant_id, new.id, names)
    except Exception:  # noqa: BLE001
        logger.warning("Entity linking failed for corrected memory %s", new.id, exc_info=True)
    _changed(tenant_id)
    return {
        "id": str(new.id),
        "content": new.content,
        "status": "active",
        "replaces": {"id": str(old.id), "content": replaced, "status": "superseded"},
    }
