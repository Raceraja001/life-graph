"""Nightly: active memories without a form slot get one, like sleep sorting the day.

New facts get their slot when they are extracted (core/slots.py). Older ones,
and any the extractor left without one, are asked about here once each, with
the extractor's rules, and normalised by the same guards. A memory checked and
given no slot is marked ``slot_checked`` so it is not asked about again.

It never replaces anything by itself. When several active memories take the
same slot, the newest is the current value (the card shows the newest), and
each older one is offered for replacement as a deferred contradiction approval:
Keep applies it, undoably; Drop leaves both.

Local model only: the memories are the owner's.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

#: Most memories asked about per tenant per night.
CAP = 40

PROMPT = """\
You assign form slots to facts the owner told their assistant. A slot is a short
key "topic.field" for a fact that is a firm, current, single value about the
owner or one of their family: where they live, employer, job title, manager,
phone, laptop, car, spouse, a child's school or class, birthday, age, monthly
budget, SIP amount, blood group, the day or club of a hobby. Topics: basics,
home, family, work, projects, hobbies, devices, vehicles, money, health,
learning, travel. Examples: work.employer, home.city, devices.phone,
family.spouse, family.anu.school, family.priya.birthday, money.budget,
health.blood_group. home.* is only where the OWNER lives. A fact about someone
else uses their name (family.divya.spouse). Preferences, rules, plans, and facts
that can have many values get null.
Reply as JSON: {"slot": "topic.field" or null, "subject": "owner" or the person's name}."""


def wants_slot(m: Any) -> bool:
    """An active, firm, owner-said fact with no slot that was never checked."""
    from life_graph.core.evidence import evidence_of

    props = m.properties or {}
    if props.get("slot") or props.get("slot_checked") or props.get("kind") == "episode":
        return False
    if props.get("certainty") == "hedged" or props.get("polarity") == "negate":
        return False
    return evidence_of(m.source_type, m.trust_tier, props) == "said"


async def ask_slot(content: str, subject: str | None = None) -> str | None:
    """The normalised slot for one fact, or None."""
    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings
    from life_graph.core import slots

    reply = await get_lm_client().chat_local_only(
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": content}],
        model=settings.lm_extraction_model,
        temperature=0.0,
        max_tokens=80,
        response_format={"type": "json_object"},
    )
    try:
        out = json.loads(reply or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(out, dict):
        return None
    # Whose fact it is was decided at extraction (properties.subject); the
    # model's guess here only fills in when that was not recorded.
    who = subject or str(out.get("subject") or "owner")
    return slots.normalise(out.get("slot"), subject=who, content=content)


async def plan(tenant_id: str, cap: int = CAP) -> dict[str, Any]:
    """What a fill would do: {"checked", "set": {id: slot}, "replace": [(old, new, slot)]}."""
    from sqlalchemy import select
    from sqlalchemy.orm import defer

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as session:
        rows = list(
            (
                await session.execute(
                    select(Memory)
                    .where(Memory.tenant_id == tenant_id, Memory.status == "active")
                    .order_by(Memory.created_at)
                    .options(defer(Memory.embedding))
                )
            )
            .scalars()
            .all()
        )
    todo = [m for m in rows if wants_slot(m)][:cap]
    proposed: dict[str, str | None] = {}
    for m in todo:
        try:
            proposed[str(m.id)] = await ask_slot(
                m.content or "", (m.properties or {}).get("subject")
            )
        except Exception:  # noqa: BLE001 — one failed call skips one memory, for tonight
            logger.warning("Form fill: slot question failed for %s", m.id, exc_info=True)
    holders: dict[str, list[Any]] = defaultdict(list)
    for m in rows:
        slot = (m.properties or {}).get("slot") or proposed.get(str(m.id))
        if slot:
            holders[slot].append(m)
    replace: list[tuple[str, str, str]] = []
    for slot, ms in holders.items():
        if len(ms) < 2 or not any(str(m.id) in proposed for m in ms):
            continue  # one value, or a clash that is not new tonight
        ms.sort(key=lambda m: m.created_at)
        newest = ms[-1]
        replace += [(str(old.id), str(newest.id), slot) for old in ms[:-1]]
    return {
        "checked": [str(m.id) for m in todo if str(m.id) in proposed],
        "set": {k: v for k, v in proposed.items() if v},
        "replace": replace,
    }


async def fill(tenant_id: str, cap: int = CAP) -> dict[str, int]:
    """Give unchecked active memories their slot and offer same-slot replacements."""
    from sqlalchemy import text

    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.database import async_session

    todo = await plan(tenant_id, cap)
    async with async_session() as session:
        for mid in todo["checked"]:
            slot = todo["set"].get(mid)
            patch = {"slot": slot, "slot_backfilled": True} if slot else {"slot_checked": True}
            await session.execute(
                text(
                    "UPDATE memories SET properties = COALESCE(properties, '{}'::jsonb) "
                    "|| CAST(:patch AS jsonb) WHERE id = :id AND tenant_id = :t "
                    "AND status = 'active' AND NOT (COALESCE(properties, '{}'::jsonb) ? 'slot')"
                ),
                {"patch": json.dumps(patch), "id": mid, "t": tenant_id},
            )
        await session.commit()
    if todo["replace"]:
        from life_graph.api.dependencies import get_memory_manager

        manager = get_memory_manager()
        with tenant_scope(tenant_id):
            for old, new, slot in todo["replace"]:
                await manager._queue_contradiction_approval(
                    old,
                    new,
                    f"Same form slot ({slot}): the newer value replaces it.",
                    applied=False,
                )
    if todo["set"]:
        from life_graph.services import profile_card

        profile_card.invalidate(tenant_id)
    report = {
        "checked": len(todo["checked"]),
        "slotted": len(todo["set"]),
        "replacements_offered": len(todo["replace"]),
    }
    logger.info("Form fill for %s: %s", tenant_id, report)
    return report
