#!/usr/bin/env python3
"""Fill the entity index (migration 053) from memories stored before it existed.

1. Every active or pending memory's ``properties.entities`` (what the
   extractor named) is linked under its normalised key.
2. Then every active memory is checked for already-known entity names in its
   text (day summaries carry no entity list of their own).

Dry run by default: prints what it would link. Idempotent: links are
"on conflict do nothing" and mentions count new links only, so re-running
only adds what is new.

Usage:
    python scripts/backfill_entities.py --tenant raja
    python scripts/backfill_entities.py --tenant raja --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from sqlalchemy import text


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    from life_graph.services import entities
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = (
            await s.execute(
                text(
                    "select id, content, coalesce(properties->'entities', '[]'::jsonb) "
                    "from memories where tenant_id=:t and status in ('active','pending')"
                ),
                {"t": args.tenant},
            )
        ).all()

    named = Counter()
    planned = 0
    for mid, _content, ents in rows:
        keys = {entities.normalize(str(e)) for e in ents or []}
        keys = {k for k in keys if entities.is_entity(k)}
        named.update(keys)
        planned += bool(keys)
        if args.apply and keys:
            await entities.link(args.tenant, mid, list(ents))
    print(f"{planned} of {len(rows)} memories name entities; {len(named)} distinct")
    print("most mentioned:", ", ".join(f"{k} ({n})" for k, n in named.most_common(15)))

    if args.apply:
        text_links = 0
        for mid, content, ents in rows:
            found = await entities.known_in_text(args.tenant, content or "")
            if found:
                text_links += await entities.link(args.tenant, mid, [n for _, n in found])
        print(f"applied; plus {text_links} links from names found in memory text")
    else:
        print("dry run: nothing written (use --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
