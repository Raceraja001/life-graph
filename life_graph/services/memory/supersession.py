"""Supersession: one memory replaced by another, and the undo (ADR M8 §5.2).

Every writer that replaces a memory goes through :func:`apply`, and every
writer that takes a replacement back goes through :func:`undo` or
:func:`restore_replaced_by`. Before 2026-11-28 the same few column writes were
copied by hand into five places (``MemoryManager.supersede``,
``tools/memory_search.py`` ``_supersede``, the approvals' deferred supersede,
merge and undo). This module holds them once, with no change in what they
write.

A supersede writes, on rows of ONE tenant only:

- old: ``status = 'superseded'``, ``superseded_by = new.id``,
  ``updated_at = now`` and ``properties.superseded_at`` (when we stopped
  believing it; retrieval.is_known_at reads it), plus any *note* keys
  (a merge adds ``merged_into``);
- new: ``supersedes = old.id``, and ``status = 'active'`` when asked to.

By default it does NOT write ``valid_until``: a supersede ends our belief,
not (by itself) the old fact's truth in the world. With ``world_change=True``
(ADR step 5, behind the ``ingest_supersession_tiers`` flag) it also ends the
old fact's world time, but only on a real world change: the new fact has a
known world start of its own (:func:`world_start`) and is not a correction.
Then ``old.valid_until`` = that start, and ``properties.valid_until_by =
"supersession"`` says who set it, so an undo clears only that one.

The rule is "a correction keeps no ``valid_until``; only a known new start
ends the old fact". Two owner acts also set ``valid_until`` and are left as
they are: ``/deny`` (storage/postgres.py ``deny``) and the stale-belief
answers in services/identity.py set it to *now*. There the owner says in so
many words that the fact is no longer true, so the end is the owner's own,
not inferred here. They carry no ``valid_until_by``, so no supersession undo
ever clears them, and :func:`apply` never overwrites a ``valid_until`` that
is already set.

It writes no approval and emits no event. Each caller still files its own
contradiction approval, as before.

Decisions follow (ADR M8 §5.4, only with ``settings.decision_lifecycle``):
after an applied supersede the caller awaits :func:`mirror_decisions`, and
after an undo :func:`undo_decision_mirror` (:func:`restore_replaced_by` does
it itself). A *candidate* decision linked to the old memory is then
superseded by the new memory's decision, and the undo takes it back. With
the setting off both return at once and read nothing.

The confidence tiers of ADR §5.2 (high, medium, low, none) are decided by
:func:`slot_tier` and :func:`possible_updates`; the low tier's daily cap is
:func:`file_possible_update`. The save path (core/memory_manager.py) uses them
only with the flag on.

Same slot means the same canonical key, and, with ``ingest_slot_pairing`` also
on, one attribute filed under two keys (:func:`same_attribute`,
:func:`slot_pairs`): the local model's keys are free text and drift between
messages (``money.budget`` one day, ``work.salary`` the next, for the same
"take-home salary"). No list of attributes is added: the pair is found from the
two sentences and the two keys the tenant's own memories already carry.

Callers keep their own rules through parameters: which old and new statuses
are allowed (``old_statuses`` / ``new_statuses``), whether the new memory is
activated, and whether the rows are locked while they are read (:func:`load`).
The functions only change ORM objects; the caller's session commits or
flushes, so the supersede lands in the caller's one transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text

from life_graph.connectors.tools import user_tz
from life_graph.core import slots
from life_graph.core.trust import TrustTier
from life_graph.models.db import Approval, Memory
from life_graph.services import decision_lifecycle
from life_graph.services.contradiction import _details, differs_in_detail, differs_in_scope
from life_graph.services.memory.typed_links import _stem, tokens
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Statuses a new memory may have for the approvals' deferred supersede.
PENDING_OR_ACTIVE = ("pending", "active")

#: Who set a ``valid_until`` written here (``properties.valid_until_by``).
#: Undo clears a ``valid_until`` only when it carries this mark.
VALID_UNTIL_BY = "supersession"
#: Text other people wrote (core/trust.py). It never supersedes the owner's
#: own facts and never makes a low-tier review item (ADR §5.2 "None").
OUTSIDE_TIERS = frozenset({TrustTier.EXTERNAL.value, TrustTier.HOSTILE_POSSIBLE.value})
#: How sure the extractor must be for a same-slot change to apply at once.
HIGH_TIER_MIN_CONFIDENCE = 0.9
#: Most low-tier "possible update" items a tenant gets per day. More are
#: counted on the day's last item (``payload.not_queued``), not queued: on
#: 2026-10-22 the review queue jammed at 3,668.
LOW_TIER_DAILY_CAP = 5
LOW_TIER_TITLE = "Possible update to review"


def _as_uuid(value: Any) -> uuid.UUID | None:
    """*value* as a UUID, or None when it is not one."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def load(
    session: AsyncSession,
    tenant_id: str,
    old_id: Any,
    new_id: Any,
    *,
    lock: bool = False,
) -> tuple[Memory | None, Memory | None]:
    """The old and new memories, each only if it belongs to *tenant_id*.

    A missing id, an id that is not a UUID, or a row of another tenant comes
    back as None, so :func:`apply` refuses it. ``lock`` takes a row lock
    (``FOR UPDATE``) on both rows until the caller's transaction ends: what a
    single ``UPDATE ... WHERE status = 'active'`` gave the correction path,
    so two replacements of one fact cannot both win.
    """
    ids = [i for i in (_as_uuid(old_id), _as_uuid(new_id)) if i is not None]
    if not ids:
        return None, None
    query = (
        select(Memory)
        .where(Memory.id.in_(ids), Memory.tenant_id == tenant_id)
        # One order for every caller: two locks taken in the same order
        # cannot deadlock each other.
        .order_by(Memory.id)
    )
    if lock:
        query = query.with_for_update()
    rows = {row.id: row for row in (await session.execute(query)).scalars().all()}
    return rows.get(_as_uuid(old_id)), rows.get(_as_uuid(new_id))


def apply(
    tenant_id: str,
    old: Memory | None,
    new: Memory | None,
    *,
    why: str,
    old_statuses: tuple[str, ...] | None = ("active",),
    new_statuses: tuple[str, ...] | None = None,
    activate_new: bool = False,
    note: Mapping[str, Any] | None = None,
    world_change: bool = False,
    now: datetime | None = None,
) -> bool:
    """Mark *old* replaced by *new*. Returns whether it happened.

    Refused (nothing changes) when either memory is missing, either is not
    *tenant_id*'s, they are the same row, *old*'s status is not in
    ``old_statuses`` or *new*'s is not in ``new_statuses`` (``None`` means
    any status). ``activate_new`` makes *new* active too (the owner agreeing
    that it replaces the old one is agreeing to it). ``note`` adds keys to
    *old*'s properties, such as a merge's ``merged_into``.

    ``why`` is only logged. ``world_change=True`` also ends *old*'s world time
    at *new*'s start when that is a real world change (:func:`world_end`):
    ``old.valid_until`` is set and marked ``valid_until_by = "supersession"``.
    A correction, a new fact with no world time of its own, or an old fact
    that already has a ``valid_until`` gets none.
    """
    refused = _refusal(tenant_id, old, new, old_statuses, new_statuses)
    if refused is not None or old is None or new is None:
        logger.debug("Supersede refused (%s): %s", refused, why)
        return False
    stamp = now or datetime.now(UTC)
    end = world_end(old, new) if world_change else None
    if activate_new:
        new.status = "active"
    old.status = "superseded"
    old.superseded_by = new.id
    old.updated_at = stamp
    # Reassigned, never mutated: an in-place change of a JSONB dict is not
    # change-tracked by the ORM.
    old.properties = {
        **(old.properties or {}),
        **(note or {}),
        "superseded_at": stamp.isoformat(),
        **({"valid_until_by": VALID_UNTIL_BY} if end is not None else {}),
    }
    if end is not None:
        old.valid_until = end
    new.supersedes = old.id
    logger.debug("Superseded %s -> %s: %s", str(old.id)[:8], str(new.id)[:8], why)
    return True


def _aware(value: Any) -> datetime | None:
    """*value* as an aware datetime (a naive one is UTC), or None."""
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def world_start(new: Any) -> datetime | None:
    """When *new*'s fact started being true in the world, if it says so.

    Known when the row carries a ``properties.world_time`` start (set by the
    world-time rules, ADR §5.1; an end alone, ``world_time.end``, is not a
    start) or its ``valid_from`` is earlier than its recorded time
    (``created_at``), to the second: ``valid_from`` = recorded is how "no world
    time" is spelled (snapshot.world_time_known). A correction ("actually it
    is Anna Nagar") has no start here: the old value was never true, so it
    must not get an end.
    """
    props = getattr(new, "properties", None) or {}
    if props.get("correction"):
        return None
    start = _aware(getattr(new, "valid_from", None))
    if start is None:
        return None
    world = props.get("world_time")
    if isinstance(world, dict) and world.get("start"):
        return start
    recorded = _aware(getattr(new, "created_at", None))
    if recorded is not None and int(start.timestamp()) < int(recorded.timestamp()):
        return start
    return None


def world_end(old: Any, new: Any, *, old_valid_from: datetime | None = None) -> datetime | None:
    """The ``valid_until`` a world change gives *old*, or None for no end.

    None when *new* has no known start (:func:`world_start`), when *old*
    already has a ``valid_until`` (the extractor's "until Friday", the
    owner's ``/deny``: never overwritten), or when the start is not after
    *old*'s own start (an end before the beginning is not a change).
    ``old_valid_from`` overrides *old*'s column when the caller is moving it.
    """
    start = world_start(new)
    if start is None or getattr(old, "valid_until", None) is not None:
        return None
    began = _aware(old_valid_from) or _aware(getattr(old, "valid_from", None))
    if began is not None and start <= began:
        return None
    return start


def slot_tier(
    *,
    new_active: bool,
    trust_tier: str | None,
    confidence: float,
    polarity: str = "affirm",
    certainty: str = "firm",
) -> str:
    """ADR §5.2 tier of a same-slot (S1) change: ``"high"`` or ``"medium"``.

    High (applied at once, undoable) only when the new fact is the owner's
    own (trust tier ``self``), already active, firm, affirmed and at
    confidence 0.9 or more. Anything else waits for the owner (medium). The
    caller has already dropped old values said after the new one
    (memory_manager ``_older_and_newer``) and only finds active old values.
    """
    if (
        new_active
        and trust_tier == TrustTier.SELF.value
        and confidence >= HIGH_TIER_MIN_CONFIDENCE
        and polarity != "negate"
        and certainty != "hedged"
    ):
        return "high"
    return "medium"


def same_subject(subject: str | None, old_properties: Mapping[str, Any] | None) -> bool:
    """Whether a new fact about *subject* and an old memory are about one person.

    S2 of ADR §5.2: a detector hit is a supersession only between facts with
    the same ``subject`` ("owner" when unset, as the save path stores it).
    """
    theirs = (old_properties or {}).get("subject") or "owner"
    return (subject or "owner") == theirs


def possible_updates(
    *,
    content: str,
    subject: str | None,
    changes_over_time: bool,
    slot: str | None,
    trust_tier: str | None,
    context: Mapping[str, Any] | None,
    candidates: Iterable[tuple[Any, float]],
    taken: set[str],
    low: float,
    high: float,
) -> list[tuple[str, str]]:
    """Low-tier pairs (ADR §5.2): old memories the new fact may update.

    Each must hold: an active old memory not already a slot or detector pair
    (*taken*), the same subject and scope, ``changes_over_time`` on both, a
    similarity in ``[low, high)`` (the contradiction threshold up to the
    dedup threshold), different details, and not two different slots. Never
    from outside text (:data:`OUTSIDE_TIERS`). Returns (old id, reason): they
    become review items only, never a supersede.
    """
    if trust_tier in OUTSIDE_TIERS or not changes_over_time:
        return []
    found: list[tuple[str, str]] = []
    for memory, score in candidates:
        props = getattr(memory, "properties", None) or {}
        if str(memory.id) in taken or getattr(memory, "status", None) != "active":
            continue
        if not props.get("changes_over_time") or not (low <= score < high):
            continue
        if slot and props.get("slot"):
            continue  # both have slots: the same one is S1, different ones differ
        if not same_subject(subject, props) or differs_in_scope(context, props):
            continue
        old_text = getattr(memory, "content", "") or ""
        if not differs_in_detail(content, old_text):
            continue
        preview = " ".join(old_text.split())[:120]
        found.append((str(memory.id), f"Possible update (was: {preview})"))
    return found


#: The verbs a frame ends at: "<attribute> is <value>". Not "was": two past
#: values can both have been true.
_COPULAS = frozenset({"is", "are"})
#: Words that may stand between the verb and the value ("is a Nexon", "is now ₹48,000").
_VALUE_LEAD = frozenset({"a", "an", "the", "now", "currently", "still", "about", "around"})


def _words(text: str) -> list[str]:
    """Lower-case words of any script (the D10 rule, typed_links.tokens), plurals
    and possessives folded ("owner's" and "owners" are "owner")."""
    return [_stem(w) for w in tokens(text)]


def _frame(words: list[str]) -> tuple[list[str], list[str]] | None:
    """The words before the first "is"/"are" (the attribute) and after it (the value)."""
    for i, word in enumerate(words):
        if word in _COPULAS:
            return words[:i], words[i + 1 :]
    return None


def _value(after: list[str], details: set[str]) -> tuple[bool, str | None] | None:
    """How the value after the verb starts: (a number?, the word after the value).

    The value is a run of numbers, names, dates, number or colour words
    (contradiction._details). None when the words after the verb do not start
    with one: "is credited on the 1st" says something else about the attribute.
    """
    i = 0
    while i < len(after) and after[i] in _VALUE_LEAD:
        i += 1
    j = i
    while j < len(after) and (any(c.isdigit() for c in after[j]) or after[j] in details):
        j += 1
    if j == i:
        return None
    return any(c.isdigit() for c in after[i]), after[j] if j < len(after) else None


def _key_words(key: str) -> tuple[set[str], set[str]]:
    """All the words of a slot key after its topic, and those of its last part
    (the field): ``family.arjun.take_home_pay`` -> ({arjun, take, home, pay},
    {take, home, pay})."""
    parts = key.split(".")[1:]
    every = {_stem(w) for part in parts for w in part.split("_") if w}
    field = {_stem(w) for w in parts[-1].split("_") if w} if parts else set()
    return every, field


def same_attribute(new_slot: str, new_content: str, old_slot: str, old_content: str) -> bool:
    """Whether two facts filed under two different slot keys are one attribute changing.

    Deterministic and narrow on purpose: a wrong pair supersedes a true fact,
    while a missed pair only leaves two values to review. All must hold:

    * both sentences say "<attribute> is <value>" with the very same words
      before "is"/"are" ("The owner's take-home salary is ...");
    * neither key names a word that only one of the two sentences has (a
      second child's name, "account", "date");
    * at least one key's field is in those shared words, so a key names the
      attribute (``work.salary``; ``money.budget`` names nothing there and is
      only the model's other spelling). When both keys name it from two
      different topics (``money.goal``, ``health.goal``) the model kept them
      apart on purpose, and so do we;
    * both values start the same way (both a number, or both a name) and are
      followed by the same word ("₹1,50,000 a month" / "₹1,80,000 a month"),
      and they differ (contradiction.differs_in_detail).

    Words are split by the D10 rule (typed_links.tokens), so Tamil script stays whole.
    """
    if not new_slot or not old_slot or new_slot == old_slot:
        return False
    new_words, old_words = _words(new_content), _words(old_content)
    new_frame, old_frame = _frame(new_words), _frame(old_words)
    if new_frame is None or old_frame is None or new_frame[0] != old_frame[0]:
        return False
    attribute = set(new_frame[0])
    only_one = set(new_words) ^ set(old_words)
    named: list[bool] = []
    for key in (new_slot, old_slot):
        every, field = _key_words(key)
        if every & only_one:
            return False
        named.append(bool(field) and field <= attribute)
    if not any(named):
        return False
    if all(named) and slots.topic_of(new_slot) != slots.topic_of(old_slot):
        return False
    new_value = _value(new_frame[1], {d.lower() for d in _details(new_content)})
    old_value = _value(old_frame[1], {d.lower() for d in _details(old_content)})
    if new_value is None or new_value != old_value:
        return False
    return differs_in_detail(new_content, old_content)


def slot_pairs(
    *,
    content: str,
    slot: str,
    subject: str | None,
    context: Mapping[str, Any] | None,
    candidates: Iterable[tuple[Any, float]],
    taken: set[str],
) -> list[tuple[str, str]]:
    """Active memories that hold the new fact's attribute under another slot key.

    Read from the save path's own similarity candidates (no extra query), each
    must be active, firm and affirmed, not already paired (*taken*), about the
    same subject and scope, and carry a slot that, read through today's rules
    (core/slots.py ``normalise``), is :func:`same_attribute` as *slot*. They are
    same-slot (S1) pairs: :func:`slot_tier` decides high or medium. Only with
    ``ingest_slot_pairing`` (and the tiers) on. Returns (old id, reason).
    """
    found: list[tuple[str, str]] = []
    for memory, _score in candidates:
        props = getattr(memory, "properties", None) or {}
        if str(memory.id) in taken or getattr(memory, "status", None) != "active":
            continue
        if props.get("polarity") == "negate" or props.get("certainty") == "hedged":
            continue
        if not same_subject(subject, props) or differs_in_scope(context, props):
            continue
        old_text = getattr(memory, "content", "") or ""
        theirs = slots.normalise(
            props.get("slot"), subject=props.get("subject") or "owner", content=old_text
        )
        if not theirs or not same_attribute(slot, content, theirs, old_text):
            continue
        preview = " ".join(old_text.split())[:120]
        found.append((str(memory.id), f"New value for {slot}, filed as {theirs} (was: {preview})"))
    return found


def _day_start(now: datetime) -> datetime:
    """Midnight of *now*'s day in the owner's timezone."""
    tz = user_tz()
    return datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)


async def file_possible_update(
    tenant_id: str, old_id: str, new_id: str, reason: str, *, now: datetime | None = None
) -> bool:
    """Queue one low-tier "possible update" review item, within the daily cap.

    A contradiction approval with ``applied: false`` and ``payload.confidence
    = "low"``: nothing changes unless the owner approves it. At most
    :data:`LOW_TIER_DAILY_CAP` per tenant per day (owner's timezone); past
    that the item is counted on the day's last one (``payload.not_queued``)
    instead. Returns whether an item was queued. Never raises: a failure here
    costs the review item, never the memory.
    """
    stamp = now or datetime.now(UTC)
    ref = f"{old_id}|{new_id}"
    try:
        async with async_session() as session:
            mine = (
                Approval.tenant_id == tenant_id,
                Approval.kind == "contradiction",
                Approval.source == "judgment",
            )
            seen = await session.execute(
                select(Approval.id).where(*mine, Approval.source_ref == ref)
            )
            if seen.first():
                return False
            today = (
                *mine,
                Approval.payload["confidence"].astext == "low",
                Approval.created_at >= _day_start(stamp),
            )
            count = (
                await session.execute(select(func.count(Approval.id)).where(*today))
            ).scalar_one()
            if count >= LOW_TIER_DAILY_CAP:
                last = (
                    await session.execute(
                        select(Approval)
                        .where(*today)
                        .order_by(Approval.created_at.desc())
                        .limit(1)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if last is not None:
                    payload = last.payload or {}
                    last.payload = {**payload, "not_queued": int(payload.get("not_queued", 0)) + 1}
                    await session.commit()
                logger.info("Low-tier review item over the daily cap: counted, not queued")
                return False
            session.add(
                Approval(
                    tenant_id=tenant_id,
                    kind="contradiction",
                    source="judgment",
                    source_ref=ref,
                    title=LOW_TIER_TITLE,
                    detail=reason,
                    payload={
                        "memory_id_old": str(old_id),
                        "memory_id_new": str(new_id),
                        "applied": False,
                        "confidence": "low",
                    },
                )
            )
            await session.commit()
            return True
    except Exception:  # noqa: BLE001 — a review item never costs the memory
        logger.warning("Failed to queue a low-tier review item", exc_info=True)
        return False


def _refusal(
    tenant_id: str,
    old: Memory | None,
    new: Memory | None,
    old_statuses: tuple[str, ...] | None,
    new_statuses: tuple[str, ...] | None,
) -> str | None:
    """Why :func:`apply` must not act, or None when it may."""
    if old is None or new is None:
        return "missing"
    if old.tenant_id != tenant_id or new.tenant_id != tenant_id:
        return "other tenant"
    if old.id == new.id:
        return "same memory"
    if old_statuses is not None and old.status not in old_statuses:
        return f"old is {old.status}"
    if new_statuses is not None and new.status not in new_statuses:
        return f"new is {new.status}"
    return None


def undo(tenant_id: str, old: Memory | None, new: Memory | None) -> bool:
    """Take back the supersede of *old* by *new* (a rejected contradiction).

    Only while *old* is still in the state :func:`apply` left it: superseded,
    and by *new* when *new* is given (a later edit is never overwritten).
    *old* becomes active again, loses ``superseded_by`` and
    ``properties.superseded_at``, and *new* loses ``supersedes`` when it
    points at *old*. A ``valid_until`` goes too, but only one :func:`apply`
    set (``valid_until_by = "supersession"``): an end the owner or the
    extractor gave stays. Returns whether anything was restored.
    """
    if old is None or old.tenant_id != tenant_id:
        return False
    if new is not None and new.tenant_id != tenant_id:
        return False  # never read or write another tenant's row
    if old.status != "superseded":
        return False
    if new is not None and old.superseded_by != new.id:
        return False
    old.status = "active"
    old.superseded_by = None
    # Undone on every timeline: without this the restored fact still read as
    # replaced to a question "as of now" (retrieval.is_known_at).
    props = old.properties or {}
    if props.get("valid_until_by") == VALID_UNTIL_BY:
        old.valid_until = None
    old.properties = {
        k: v
        for k, v in props.items()
        if k != "superseded_at"
        and not (k == "valid_until_by" and props.get("valid_until_by") == VALID_UNTIL_BY)
    }
    if new is not None and new.supersedes == old.id:
        new.supersedes = None
    return True


async def mirror_decisions(
    session: AsyncSession, tenant_id: str, old: Memory | None, new: Memory | None
) -> bool:
    """After :func:`apply` of *old* by *new*: the linked candidate decision follows.

    services/decision_lifecycle.py ``mirror_memory_supersede``; does nothing
    unless ``settings.decision_lifecycle``. Same session, so the decision
    moves in the memory supersede's own transaction.
    """
    if old is None or new is None:
        return False
    return await decision_lifecycle.mirror_memory_supersede(session, tenant_id, old.id, new.id)


async def undo_decision_mirror(
    session: AsyncSession, tenant_id: str, *, old_id: Any = None, new_id: Any = None
) -> int:
    """After :func:`undo`: the decisions that mirrored that supersede move back.

    services/decision_lifecycle.py ``undo_memory_mirror``; does nothing unless
    ``settings.decision_lifecycle``.
    """
    return await decision_lifecycle.undo_memory_mirror(
        session, tenant_id, old_memory_id=old_id, new_memory_id=new_id
    )


async def restore_replaced_by(session: AsyncSession, tenant_id: str, new_id: Any) -> None:
    """Bring back every memory of *tenant_id* that *new_id* replaced.

    For taking a saved or corrected memory back (api/jarvis.py undo_save,
    the memory page's drop): what it replaced is current again. A
    near-duplicate merged into it (``merged_into``) is not an earlier value
    and stays folded away. *new_id*'s own ``supersedes`` is left as it is.
    A ``valid_until`` that :func:`apply` set (``valid_until_by =
    "supersession"``) is cleared with its mark; any other stays.
    Runs in the caller's transaction; the caller commits.
    """
    await session.execute(
        text(
            # superseded_at goes too: an undo restores the old value as
            # current belief on every timeline (retrieval.is_known_at).
            # Every SET expression reads the row as it was, so the CASEs see
            # the mark before it is removed.
            "UPDATE memories SET status = 'active', superseded_by = NULL, updated_at = NOW(),"
            " valid_until = CASE WHEN properties->>'valid_until_by' = :by"
            " THEN NULL ELSE valid_until END,"
            " properties = (COALESCE(properties, '{}'::jsonb) - 'superseded_at')"
            " - CASE WHEN properties->>'valid_until_by' = :by"
            " THEN 'valid_until_by' ELSE '' END"
            " WHERE tenant_id = :t AND superseded_by = :id AND status = 'superseded'"
            " AND NOT (COALESCE(properties, '{}'::jsonb) ? 'merged_into')"
        ),
        {"id": new_id, "t": tenant_id, "by": VALID_UNTIL_BY},
    )
    await undo_decision_mirror(session, tenant_id, new_id=new_id)
