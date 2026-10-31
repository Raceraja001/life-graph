"""Give existing active memories their form slot (core/slots.py), by hand.

The nightly job does the same (services/form_fill.py, workers/form_fill.py,
at most 40 memories a night); this runs it now, for one tenant. It never
replaces anything by itself: when several memories take the same slot, the
newest is the current value and each older one is offered for replacement as
an approval.

Dry run unless --apply.

    PYTHONPATH=. python scripts/backfill_slots.py --tenant raja [--apply] [--cap 40]
"""

from __future__ import annotations

import argparse
import asyncio


async def main(tenant: str, apply: bool, cap: int) -> None:
    from life_graph.services import form_fill

    if apply:
        print(await form_fill.fill(tenant, cap))
        return
    todo = await form_fill.plan(tenant, cap)
    print(f"{len(todo['checked'])} checked · {len(todo['set'])} slots to set")
    for mid, slot in sorted(todo["set"].items(), key=lambda kv: kv[1]):
        print(f"  {slot:<32} {mid}")
    for old, new, slot in todo["replace"]:
        print(f"  REPLACE {slot}: {old} -> {new}")
    print("dry run: nothing written (--apply to set them)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cap", type=int, default=40)
    a = ap.parse_args()
    asyncio.run(main(a.tenant, a.apply, a.cap))
