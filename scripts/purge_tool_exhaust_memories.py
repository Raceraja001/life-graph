#!/usr/bin/env python3
"""Delete memories that were extracted from tool-exhaust captures.

Why this exists
---------------
Every tool call a coding agent makes arrives as a capture on the
``tool_exhaust`` surface. Until ``capture_no_extract_surfaces`` existed, those
captures went through the same LLM extraction as real content, so each shell
command became several memories along the lines of *"The script starts with a
shebang line '#!/bin/bash' indicating it is a Bash script."*

On the author's own instance that was 4,752 of 4,988 memories — all pending,
and all of it feeding back into the next session through recall. The pipeline
fix stops new ones; this removes the ones already stored.

What it deletes
---------------
Only rows that are **both** ``source_type = 'capture'`` and
``properties->>'surface' = 'tool_exhaust'``. Memories from any other surface,
and the ``capture_events`` rows themselves (which are the activity trail worth
keeping), are left alone.

Usage
-----
    python scripts/purge_tool_exhaust_memories.py              # dry run
    python scripts/purge_tool_exhaust_memories.py --apply      # delete
    python scripts/purge_tool_exhaust_memories.py --apply --tenant raja

Deletion is irreversible, so ``--apply`` is required; without it the script
only reports. Take a backup first (``scripts/backup.sh``) if the instance
holds anything you cannot re-derive.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text

from life_graph.config import settings

SURFACE = "tool_exhaust"

#: Deleted in batches so a large purge neither holds one long transaction nor
#: builds a single statement over tens of thousands of ids.
BATCH = 500

_WHERE = """
    source_type = 'capture'
    AND properties->>'surface' = :surface
    {tenant_clause}
"""


def _where(tenant: str | None) -> str:
    return _WHERE.format(tenant_clause="AND tenant_id = :tenant" if tenant else "")


def _params(tenant: str | None) -> dict[str, str]:
    params = {"surface": SURFACE}
    if tenant:
        params["tenant"] = tenant
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="actually delete (default is a dry run)"
    )
    parser.add_argument("--tenant", help="limit to one tenant (default: all)")
    args = parser.parse_args()

    engine = create_engine(settings.database_url_sync)
    params = _params(args.tenant)
    where = _where(args.tenant)

    with engine.begin() as conn:
        total = conn.execute(text("SELECT count(*) FROM memories"), params).scalar_one()
        target = conn.execute(
            text(f"SELECT count(*) FROM memories WHERE {where}"), params
        ).scalar_one()
        print(f"memories: {total}")
        print(f"  from {SURFACE} captures: {target}")
        print(f"  keeping: {total - target}")

        if not target:
            print("\nNothing to do.")
            return 0

        sample = conn.execute(
            text(f"SELECT left(content, 100) FROM memories WHERE {where} LIMIT 3"), params
        ).scalars()
        print("\nsample of what would go:")
        for row in sample:
            print(f"  - {row}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to delete.")
        return 0

    deleted = 0
    while True:
        with engine.begin() as conn:
            # Delete by primary key from a bounded subselect: the predicate is a
            # jsonb lookup with no index behind it, so re-scanning the whole
            # table per batch would make the purge quadratic.
            result = conn.execute(
                text(
                    f"""
                    DELETE FROM memories
                    WHERE id IN (
                        SELECT id FROM memories WHERE {where} LIMIT {BATCH}
                    )
                    """
                ),
                params,
            )
        if not result.rowcount:
            break
        deleted += result.rowcount
        print(f"  deleted {deleted}/{target}…")

    with engine.begin() as conn:
        remaining = conn.execute(text("SELECT count(*) FROM memories"), params).scalar_one()
    print(f"\nDeleted {deleted}. {remaining} memories remain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
