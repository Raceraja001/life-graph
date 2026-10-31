"""Give existing active memories their form slot (core/slots.py), once.

Memories saved before slots existed have none, so the owner's form starts
empty. This asks the local extraction model for each active memory's slot,
with the same rules as extraction, and normalises it. It never replaces
anything: when two memories would take the same slot, neither gets it and both
are listed, for the owner to settle.

Dry run unless --apply; --apply writes at most --cap slots.

    PYTHONPATH=. python scripts/backfill_slots.py --tenant raja [--apply] [--cap 40]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict

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


async def main(tenant: str, apply: bool, cap: int) -> None:
    from sqlalchemy import select

    from life_graph.api.dependencies import get_lm_client
    from life_graph.config import settings
    from life_graph.core import slots
    from life_graph.core.evidence import evidence_of
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = (
            (
                await s.execute(
                    select(Memory).where(Memory.tenant_id == tenant, Memory.status == "active")
                )
            )
            .scalars()
            .all()
        )
    candidates = []
    for m in rows:
        props = m.properties or {}
        if props.get("slot") or props.get("kind") == "episode":
            continue
        if props.get("certainty") == "hedged" or props.get("polarity") == "negate":
            continue
        if evidence_of(m.source_type, m.trust_tier, props) != "said":
            continue
        candidates.append(m)

    client = get_lm_client()
    proposed: dict[str, list] = defaultdict(list)
    for m in candidates:
        reply = await client.chat_local_only(
            messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": m.content}],
            model=settings.lm_extraction_model,
            temperature=0.0,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        try:
            out = json.loads(reply or "{}")
        except json.JSONDecodeError:
            out = {}
        key = slots.normalise(
            out.get("slot"), subject=str(out.get("subject") or "owner"), content=m.content
        )
        if key:
            proposed[key].append(m)

    unique = {k: ms[0] for k, ms in proposed.items() if len(ms) == 1}
    clashes = {k: ms for k, ms in proposed.items() if len(ms) > 1}
    print(f"{len(rows)} active · {len(candidates)} checked · {len(unique)} slots to set · {len(clashes)} clashes")
    for k, m in sorted(unique.items()):
        print(f"  {k:<32} {m.content[:90]}")
    for k, ms in clashes.items():
        print(f"  CLASH {k}: " + " | ".join(x.content[:60] for x in ms))
    if not apply:
        print("dry run: nothing written (--apply to set them)")
        return
    from sqlalchemy import text

    written = 0
    async with async_session() as s:
        for k, m in sorted(unique.items())[:cap]:
            await s.execute(
                text(
                    "UPDATE memories SET properties = COALESCE(properties, '{}'::jsonb) || "
                    "jsonb_build_object('slot', CAST(:slot AS text), 'slot_backfilled', true) "
                    "WHERE id = :id AND tenant_id = :t AND status = 'active' "
                    "AND NOT (COALESCE(properties, '{}'::jsonb) ? 'slot')"
                ),
                {"slot": k, "id": m.id, "t": tenant},
            )
            written += 1
        await s.commit()
    from life_graph.services import profile_card

    profile_card.invalidate(tenant)
    print(f"wrote {written} slots")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cap", type=int, default=40)
    a = ap.parse_args()
    asyncio.run(main(a.tenant, a.apply, a.cap))
